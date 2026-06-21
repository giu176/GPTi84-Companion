package com.ti84relay.android.data

import android.content.Context
import androidx.room.Dao
import androidx.room.Database
import androidx.room.Entity
import androidx.room.PrimaryKey
import androidx.room.Query
import androidx.room.Room
import androidx.room.RoomDatabase
import androidx.room.Upsert

@Entity(tableName = "relay_transactions")
data class RelayTransaction(
    @PrimaryKey val transactionId: Long,
    val state: String,
    val query: String,
    val response: String? = null,
    val errorCode: String? = null,
    val errorMessage: String? = null,
    val updatedAt: Long = System.currentTimeMillis(),
)

@Dao
interface TransactionDao {
    @Upsert suspend fun upsert(transaction: RelayTransaction)
    @Query("SELECT * FROM relay_transactions WHERE transactionId = :id") suspend fun get(id: Long): RelayTransaction?
    @Query("SELECT * FROM relay_transactions ORDER BY updatedAt DESC LIMIT 50") suspend fun recent(): List<RelayTransaction>
}

@Database(entities = [RelayTransaction::class], version = 1, exportSchema = true)
abstract class TransactionDatabase : RoomDatabase() {
    abstract fun transactions(): TransactionDao

    companion object {
        fun create(context: Context): TransactionDatabase = Room.databaseBuilder(
            context, TransactionDatabase::class.java, "ti84-relay.db"
        ).build()
    }
}

