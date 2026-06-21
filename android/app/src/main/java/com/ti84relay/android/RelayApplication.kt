package com.ti84relay.android

import android.app.Application
import com.ti84relay.android.data.SecureSettings
import com.ti84relay.android.data.TransactionDatabase
import com.ti84relay.android.provider.ProviderRegistry

class RelayApplication : Application() {
    lateinit var runtime: RelayRuntime
        private set

    override fun onCreate() {
        super.onCreate()
        runtime = RelayRuntime(
            settings = SecureSettings(this),
            database = TransactionDatabase.create(this),
            providers = ProviderRegistry(),
        )
    }
}

