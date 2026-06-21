package com.ti84relay.android.data

import android.content.Context
import android.provider.Settings
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

class SecureSettings(context: Context) {
    private val preferences = context.getSharedPreferences("relay_settings", Context.MODE_PRIVATE)
    private val keyStore = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
    private val alias = "ti84-relay-provider-secrets"

    var deviceAddress: String?
        get() = preferences.getString("device_address", null)
        set(value) = preferences.edit().putString("device_address", value).apply()

    var deviceName: String?
        get() = preferences.getString("device_name", null)
        set(value) = preferences.edit().putString("device_name", value).apply()

    var activeProvider: ProviderKind
        get() = runCatching { ProviderKind.valueOf(preferences.getString("active_provider", ProviderKind.OPENAI.name)!!) }
            .getOrDefault(ProviderKind.OPENAI)
        set(value) = preferences.edit().putString("active_provider", value.name).apply()

    fun load(kind: ProviderKind): ProviderConfig {
        val prefix = kind.name.lowercase()
        return ProviderConfig(
            kind = kind,
            model = preferences.getString("${prefix}_model", kind.defaultModel) ?: kind.defaultModel,
            baseUrl = preferences.getString("${prefix}_base", kind.defaultBaseUrl) ?: kind.defaultBaseUrl,
            path = preferences.getString("${prefix}_path", kind.defaultPath) ?: kind.defaultPath,
            apiKey = decrypt(preferences.getString("${prefix}_key", null)),
            maxOutputTokens = preferences.getInt("${prefix}_max_tokens", 1024),
        )
    }

    fun save(config: ProviderConfig) {
        val prefix = config.kind.name.lowercase()
        preferences.edit()
            .putString("${prefix}_model", config.model.trim())
            .putString("${prefix}_base", config.baseUrl.trim().trimEnd('/'))
            .putString("${prefix}_path", config.path.trim())
            .putString("${prefix}_key", encrypt(config.apiKey.trim()))
            .putInt("${prefix}_max_tokens", config.maxOutputTokens.coerceIn(1, 8192))
            .apply()
    }

    private fun secretKey(): SecretKey {
        (keyStore.getKey(alias, null) as? SecretKey)?.let { return it }
        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore").run {
            init(
                KeyGenParameterSpec.Builder(alias, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                    .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                    .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                    .build()
            )
            generateKey()
        }
    }

    private fun encrypt(value: String): String? {
        if (value.isBlank()) return null
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, secretKey())
        val combined = cipher.iv + cipher.doFinal(value.toByteArray(Charsets.UTF_8))
        return Base64.encodeToString(combined, Base64.NO_WRAP)
    }

    private fun decrypt(encoded: String?): String {
        if (encoded.isNullOrBlank()) return ""
        return runCatching {
            val combined = Base64.decode(encoded, Base64.NO_WRAP)
            val cipher = Cipher.getInstance("AES/GCM/NoPadding")
            cipher.init(Cipher.DECRYPT_MODE, secretKey(), GCMParameterSpec(128, combined.copyOfRange(0, 12)))
            String(cipher.doFinal(combined.copyOfRange(12, combined.size)), Charsets.UTF_8)
        }.getOrDefault("")
    }
}

