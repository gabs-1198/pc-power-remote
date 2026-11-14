package com.pessoal.pcpower.data

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject

data class PcConfig(
    val hostname: String = "Nenhum PC pareado",
    val ipAddress: String = "",
    val macAddress: String = "",
    val port: Int = 5050,
    val pin: String = ""
)

class PcConfigStore(context: Context) {
    private val prefs = context.getSharedPreferences("pc_power_prefs", Context.MODE_PRIVATE)

    fun load(): PcConfig {
        return PcConfig(
            hostname = prefs.getString("hostname", "Nenhum PC pareado") ?: "Nenhum PC pareado",
            ipAddress = prefs.getString("ipAddress", "") ?: "",
            macAddress = prefs.getString("macAddress", "") ?: "",
            port = prefs.getInt("port", 5050),
            pin = prefs.getString("pin", "") ?: ""
        )
    }

    fun save(config: PcConfig) {
        val cleanIp = config.ipAddress.trim()
        val cleanMac = config.macAddress.trim().uppercase().replace("-", ":")
        val cleanHost = config.hostname.trim().ifEmpty { "Computador" }

        prefs.edit()
            .putString("hostname", cleanHost)
            .putString("ipAddress", cleanIp)
            .putString("macAddress", cleanMac)
            .putInt("port", config.port)
            .putString("pin", config.pin.trim())
            .apply()

        if (cleanIp.isNotEmpty() || cleanMac.isNotEmpty()) {
            addOrUpdateSavedPc(
                config.copy(
                    hostname = cleanHost,
                    ipAddress = cleanIp,
                    macAddress = cleanMac
                )
            )
        }
    }

    fun loadSavedPcs(): List<PcConfig> {
        val raw = prefs.getString("saved_pcs_json", "[]") ?: "[]"
        val list = mutableListOf<PcConfig>()
        try {
            val arr = JSONArray(raw)
            for (i in 0 until arr.length()) {
                val obj = arr.getJSONObject(i)
                list.add(
                    PcConfig(
                        hostname = obj.optString("hostname", "Computador"),
                        ipAddress = obj.optString("ipAddress", ""),
                        macAddress = obj.optString("macAddress", ""),
                        port = obj.optInt("port", 5050),
                        pin = obj.optString("pin", "")
                    )
                )
            }
        } catch (_: Exception) {
        }
        return list
    }

    private fun addOrUpdateSavedPc(config: PcConfig) {
        val current = loadSavedPcs().toMutableList()
        val idx = current.indexOfFirst {
            (config.macAddress.isNotEmpty() && it.macAddress.equals(config.macAddress, ignoreCase = true)) ||
                (config.ipAddress.isNotEmpty() && it.ipAddress == config.ipAddress)
        }
        if (idx >= 0) {
            val existingPin = if (config.pin.isNotEmpty()) config.pin else current[idx].pin
            current[idx] = config.copy(pin = existingPin)
        } else {
            current.add(0, config)
        }

        val arr = JSONArray()
        for (pc in current) {
            arr.put(
                JSONObject().apply {
                    put("hostname", pc.hostname)
                    put("ipAddress", pc.ipAddress)
                    put("macAddress", pc.macAddress)
                    put("port", pc.port)
                    put("pin", pc.pin)
                }
            )
        }
        prefs.edit().putString("saved_pcs_json", arr.toString()).apply()
    }
}
