package com.ti84relay.android.provider

import com.ti84relay.android.data.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.TimeUnit

interface AiProvider {
    suspend fun selfTest(config: ProviderConfig): ProviderHealth
    suspend fun complete(config: ProviderConfig, prompt: String): ProviderResult
}

class ProviderRegistry {
    private val client = OkHttpClient.Builder()
        .connectTimeout(20, TimeUnit.SECONDS)
        .readTimeout(120, TimeUnit.SECONDS)
        .writeTimeout(20, TimeUnit.SECONDS)
        .callTimeout(130, TimeUnit.SECONDS)
        .build()

    fun provider(kind: ProviderKind): AiProvider = when (kind) {
        ProviderKind.OPENAI -> OpenAiProvider(client)
        ProviderKind.ANTHROPIC -> AnthropicProvider(client)
        ProviderKind.GEMINI -> GeminiProvider(client)
        ProviderKind.OPENAI_COMPATIBLE -> OpenAiCompatibleProvider(client)
    }
}

abstract class JsonProvider(protected val client: OkHttpClient) : AiProvider {
    protected val mediaType = "application/json; charset=utf-8".toMediaType()

    override suspend fun selfTest(config: ProviderConfig): ProviderHealth = runCatching {
        complete(config.copy(maxOutputTokens = 16), "Reply with exactly OK.")
        ProviderHealth(true, "Provider answered successfully")
    }.getOrElse { ProviderHealth(false, (it as? ProviderFailure)?.let { f -> "${f.code}: ${f.message}" } ?: it.message ?: "Unknown error") }

    protected suspend fun execute(request: Request): JSONObject = withContext(Dispatchers.IO) {
        try {
            client.newCall(request).execute().use { response ->
                val text = response.body?.string().orEmpty()
                if (!response.isSuccessful) {
                    val code = when (response.code) {
                        401, 403 -> "AUTH_ERROR"
                        404 -> "MODEL_UNAVAILABLE"
                        408 -> "API_TIMEOUT"
                        429 -> "RATE_LIMITED"
                        in 500..599 -> "PROVIDER_ERROR"
                        else -> "BAD_REQUEST"
                    }
                    throw ProviderFailure(code, errorMessage(text, response.code), response.code == 408 || response.code == 429 || response.code >= 500)
                }
                try { JSONObject(text) } catch (error: Exception) { throw ProviderFailure("BAD_RESPONSE", "Provider returned invalid JSON") }
            }
        } catch (failure: ProviderFailure) {
            throw failure
        } catch (failure: IOException) {
            throw ProviderFailure("NETWORK_ERROR", failure.message ?: "Network request failed", true)
        }
    }

    private fun errorMessage(body: String, status: Int): String = runCatching {
        val json = JSONObject(body)
        json.optJSONObject("error")?.optString("message")
            ?: json.optString("message").takeIf { it.isNotBlank() }
            ?: "HTTP $status"
    }.getOrDefault("HTTP $status")

    protected fun validate(config: ProviderConfig, requireApiKey: Boolean = true) {
        if (requireApiKey && config.apiKey.isBlank()) throw ProviderFailure("AUTH_ERROR", "API key is missing")
        if (config.model.isBlank()) throw ProviderFailure("MODEL_UNAVAILABLE", "Model is missing")
        if (!config.baseUrl.startsWith("https://")) throw ProviderFailure("BAD_REQUEST", "HTTPS base URL is required")
    }
}

class OpenAiProvider(client: OkHttpClient) : JsonProvider(client) {
    override suspend fun complete(config: ProviderConfig, prompt: String): ProviderResult {
        validate(config)
        val body = JSONObject().put("model", config.model).put("input", prompt)
            .put("max_output_tokens", config.maxOutputTokens)
        val request = Request.Builder().url(config.baseUrl + config.path)
            .header("Authorization", "Bearer ${config.apiKey}")
            .post(body.toString().toRequestBody(mediaType)).build()
        val json = execute(request)
        val output = json.optJSONArray("output") ?: throw ProviderFailure("BAD_RESPONSE", "Missing output array")
        val text = buildString {
            for (i in 0 until output.length()) {
                val content = output.optJSONObject(i)?.optJSONArray("content") ?: continue
                for (j in 0 until content.length()) content.optJSONObject(j)?.optString("text")?.takeIf { it.isNotBlank() }?.let { append(it) }
            }
        }
        if (text.isBlank()) throw ProviderFailure("BAD_RESPONSE", "OpenAI returned no text")
        return ProviderResult(text)
    }
}

class AnthropicProvider(client: OkHttpClient) : JsonProvider(client) {
    override suspend fun complete(config: ProviderConfig, prompt: String): ProviderResult {
        validate(config)
        val body = JSONObject().put("model", config.model).put("max_tokens", config.maxOutputTokens)
            .put("messages", JSONArray().put(JSONObject().put("role", "user").put("content", prompt)))
        val request = Request.Builder().url(config.baseUrl + config.path)
            .header("x-api-key", config.apiKey).header("anthropic-version", "2023-06-01")
            .post(body.toString().toRequestBody(mediaType)).build()
        val content = execute(request).optJSONArray("content") ?: throw ProviderFailure("BAD_RESPONSE", "Missing content")
        val text = buildString { for (i in 0 until content.length()) content.optJSONObject(i)?.optString("text")?.let(::append) }
        if (text.isBlank()) throw ProviderFailure("BAD_RESPONSE", "Anthropic returned no text")
        return ProviderResult(text)
    }
}

class GeminiProvider(client: OkHttpClient) : JsonProvider(client) {
    override suspend fun complete(config: ProviderConfig, prompt: String): ProviderResult {
        validate(config)
        val parts = JSONArray().put(JSONObject().put("text", prompt))
        val body = JSONObject().put("contents", JSONArray().put(JSONObject().put("parts", parts)))
            .put("generationConfig", JSONObject().put("maxOutputTokens", config.maxOutputTokens))
        val path = config.path.replace("{model}", config.model)
        val request = Request.Builder().url(config.baseUrl + path).header("x-goog-api-key", config.apiKey)
            .post(body.toString().toRequestBody(mediaType)).build()
        val candidates = execute(request).optJSONArray("candidates") ?: throw ProviderFailure("BAD_RESPONSE", "Missing candidates")
        val outputParts = candidates.optJSONObject(0)?.optJSONObject("content")?.optJSONArray("parts")
            ?: throw ProviderFailure("BAD_RESPONSE", "Missing response parts")
        val text = buildString { for (i in 0 until outputParts.length()) outputParts.optJSONObject(i)?.optString("text")?.let(::append) }
        if (text.isBlank()) throw ProviderFailure("BAD_RESPONSE", "Gemini returned no text")
        return ProviderResult(text)
    }
}

class OpenAiCompatibleProvider(client: OkHttpClient) : JsonProvider(client) {
    override suspend fun complete(config: ProviderConfig, prompt: String): ProviderResult {
        validate(config, requireApiKey = false)
        val messages = JSONArray().put(JSONObject().put("role", "user").put("content", prompt))
        val body = JSONObject().put("model", config.model).put("messages", messages).put("max_tokens", config.maxOutputTokens)
        val builder = Request.Builder().url(config.baseUrl + config.path).post(body.toString().toRequestBody(mediaType))
        if (config.apiKey.isNotBlank()) builder.header("Authorization", "Bearer ${config.apiKey}")
        val choices = execute(builder.build()).optJSONArray("choices") ?: throw ProviderFailure("BAD_RESPONSE", "Missing choices")
        val text = choices.optJSONObject(0)?.optJSONObject("message")?.optString("content").orEmpty()
        if (text.isBlank()) throw ProviderFailure("BAD_RESPONSE", "Endpoint returned no text")
        return ProviderResult(text)
    }
}
