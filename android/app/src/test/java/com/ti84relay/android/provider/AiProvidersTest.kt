package com.ti84relay.android.provider

import com.ti84relay.android.data.ProviderConfig
import com.ti84relay.android.data.ProviderFailure
import com.ti84relay.android.data.ProviderKind
import kotlinx.coroutines.runBlocking
import okhttp3.OkHttpClient
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class AiProvidersTest {
    private lateinit var server: MockWebServer
    private val client = OkHttpClient()

    @Before fun start() { server = MockWebServer().also { it.start() } }
    @After fun stop() { server.shutdown() }

    private fun config(kind: ProviderKind) = ProviderConfig(
        kind = kind,
        model = "test-model",
        baseUrl = server.url("/").toString().trimEnd('/').replace("http://", "https://"),
        path = "/test",
        apiKey = "secret",
    )

    // Providers require HTTPS in production. MockWebServer is HTTP, so override the validation URL
    // through a client interceptor that rewrites requests back to the local test server.
    private fun testClient(): OkHttpClient = client.newBuilder().addInterceptor { chain ->
        val request = chain.request()
        chain.proceed(request.newBuilder().url(server.url(request.url.encodedPath)).build())
    }.build()

    @Test fun parsesOpenAiResponse() = runBlocking {
        server.enqueue(MockResponse().setBody("""{"output":[{"content":[{"type":"output_text","text":"hello"}]}]}"""))
        val result = OpenAiProvider(testClient()).complete(config(ProviderKind.OPENAI), "test")
        assertEquals("hello", result.text)
    }

    @Test fun parsesAnthropicResponse() = runBlocking {
        server.enqueue(MockResponse().setBody("""{"content":[{"type":"text","text":"hello"}]}"""))
        val result = AnthropicProvider(testClient()).complete(config(ProviderKind.ANTHROPIC), "test")
        assertEquals("hello", result.text)
    }

    @Test fun parsesGeminiResponse() = runBlocking {
        server.enqueue(MockResponse().setBody("""{"candidates":[{"content":{"parts":[{"text":"hello"}]}}]}"""))
        val result = GeminiProvider(testClient()).complete(config(ProviderKind.GEMINI), "test")
        assertEquals("hello", result.text)
    }

    @Test fun parsesCompatibleResponseWithoutKey() = runBlocking {
        server.enqueue(MockResponse().setBody("""{"choices":[{"message":{"content":"hello"}}]}"""))
        val result = OpenAiCompatibleProvider(testClient()).complete(
            config(ProviderKind.OPENAI_COMPATIBLE).copy(apiKey = ""), "test"
        )
        assertEquals("hello", result.text)
    }

    @Test fun mapsAuthenticationError() = runBlocking {
        server.enqueue(MockResponse().setResponseCode(401).setBody("""{"error":{"message":"bad key"}}"""))
        val failure = runCatching { OpenAiProvider(testClient()).complete(config(ProviderKind.OPENAI), "test") }.exceptionOrNull()
        assertTrue(failure is ProviderFailure)
        assertEquals("AUTH_ERROR", (failure as ProviderFailure).code)
    }

    @Test fun selfTestUsesProviderSafeTokenMinimum() = runBlocking {
        server.enqueue(MockResponse().setBody("""{"output":[{"content":[{"type":"output_text","text":"OK"}]}]}"""))
        val provider = OpenAiProvider(testClient())
        val health = provider.selfTest(config(ProviderKind.OPENAI).copy(maxOutputTokens = 1))
        assertTrue(health.healthy)
        val requestBody = server.takeRequest().body.readUtf8()
        assertTrue(requestBody.contains("\"max_output_tokens\":16"))
    }
}
