package com.ti84relay.android.data

enum class ProviderKind(val displayName: String, val defaultModel: String, val defaultBaseUrl: String, val defaultPath: String) {
    OPENAI("OpenAI", "gpt-5.5", "https://api.openai.com", "/v1/responses"),
    ANTHROPIC("Anthropic", "claude-sonnet-4-6", "https://api.anthropic.com", "/v1/messages"),
    GEMINI("Gemini", "gemini-3.5-flash", "https://generativelanguage.googleapis.com", "/v1beta/models/{model}:generateContent"),
    OPENAI_COMPATIBLE("OpenAI-compatible", "", "https://example.invalid", "/v1/chat/completions"),
}

data class ProviderConfig(
    val kind: ProviderKind,
    val model: String,
    val baseUrl: String,
    val path: String,
    val apiKey: String,
    val maxOutputTokens: Int = 1024,
)

data class ProviderResult(val text: String)

data class ProviderHealth(val healthy: Boolean, val message: String)

class ProviderFailure(val code: String, message: String, val retryable: Boolean = false) : Exception(message)

