package com.pessoal.pcpower.network

import com.pessoal.pcpower.data.PcConfig
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.io.OutputStreamWriter
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.HttpURLConnection
import java.net.Inet4Address
import java.net.InetAddress
import java.net.NetworkInterface
import java.net.URL

data class WolDiagnostics(
    val isEthernet: Boolean = true,
    val adapterName: String = "",
    val wakeArmed: Boolean = true,
    val fastStartupDisabled: Boolean = true,
    val readyForWol: Boolean = true
)

data class PcStatusResult(
    val isOnline: Boolean,
    val hostname: String? = null,
    val macAddress: String? = null,
    val ipAddress: String? = null,
    val port: Int = 5050,
    val requiresPin: Boolean = false,
    val wolDiagnostics: WolDiagnostics? = null,
    val message: String = ""
)

data class ActionResult(
    val success: Boolean,
    val message: String
)

object PcPowerClient {

    private const val DISCOVERY_UDP_PORT = 5051

    /**
     * Descobre TODOS os computadores rodando o agente na mesma rede Wi-Fi/LAN:
     * 1. Coleta todas as respostas via UDP Broadcast na porta 5051
     * 2. Caso o roteador filtre broadcast (nenhum encontrado via UDP), faz varredura paralela na sub-rede /24
     */
    suspend fun discoverAllPcsOnNetwork(httpPort: Int = 5050): List<PcStatusResult> =
        withContext(Dispatchers.IO) {
            val localIp = getPhoneLocalIp()
            val subnetPrefix = localIp?.substringBeforeLast(".", "") ?: ""
            val discoveredByKey = linkedMapOf<String, PcStatusResult>()

            // 1. Coleta todos os PCs que responderem ao Broadcast UDP na porta 5051
            try {
                DatagramSocket().use { socket ->
                    socket.broadcast = true
                    socket.soTimeout = 450
                    val payload = "DISCOVER_PCPOWER".toByteArray(Charsets.UTF_8)

                    val broadcastTargets = mutableSetOf("255.255.255.255")
                    if (subnetPrefix.isNotEmpty()) {
                        broadcastTargets.add("$subnetPrefix.255")
                    }

                    for (target in broadcastTargets) {
                        runCatching {
                            val packet = DatagramPacket(
                                payload,
                                payload.size,
                                InetAddress.getByName(target),
                                DISCOVERY_UDP_PORT
                            )
                            socket.send(packet)
                        }
                    }

                    val deadline = System.currentTimeMillis() + 900
                    val buf = ByteArray(1024)
                    while (System.currentTimeMillis() < deadline) {
                        try {
                            val recv = DatagramPacket(buf, buf.size)
                            socket.receive(recv)
                            val body = String(recv.data, 0, recv.length, Charsets.UTF_8)
                            val json = JSONObject(body)
                            val foundIp = json.optString("ip").ifEmpty { recv.address.hostAddress ?: "" }
                            val foundMac = json.optString("mac").uppercase()
                            val foundHost = json.optString("hostname", "Computador")
                            val foundPort = json.optInt("port", httpPort)
                            val diagJson = json.optJSONObject("wolDiagnostics")
                            val diag = diagJson?.let {
                                WolDiagnostics(
                                    isEthernet = it.optBoolean("isEthernet", true),
                                    adapterName = it.optString("adapterName", ""),
                                    wakeArmed = it.optBoolean("wakeArmed", true),
                                    fastStartupDisabled = it.optBoolean("fastStartupDisabled", true),
                                    readyForWol = it.optBoolean("readyForWol", true)
                                )
                            }
                            val key = if (foundMac.isNotEmpty()) foundMac else foundIp

                            if (foundIp.isNotEmpty()) {
                                discoveredByKey[key] = PcStatusResult(
                                    isOnline = true,
                                    hostname = foundHost,
                                    macAddress = foundMac,
                                    ipAddress = foundIp,
                                    port = foundPort,
                                    requiresPin = json.optBoolean("requiresPin", false),
                                    wolDiagnostics = diag,
                                    message = "Conectado a $foundHost ($foundIp)"
                                )
                            }
                        } catch (_: Exception) {
                            break
                        }
                    }
                }
            } catch (_: Exception) {
            }

            if (discoveredByKey.isNotEmpty()) {
                return@withContext discoveredByKey.values.toList()
            }

            // 2. Fallback: Varredura paralela em toda a sub-rede /24
            if (subnetPrefix.isNotEmpty()) {
                val scanned = scanSubnetAll(subnetPrefix, httpPort)
                for (item in scanned) {
                    val key = item.macAddress?.takeIf { it.isNotEmpty() } ?: (item.ipAddress ?: "")
                    if (key.isNotEmpty()) {
                        discoveredByKey[key] = item
                    }
                }
            }

            discoveredByKey.values.toList()
        }

    private suspend fun scanSubnetAll(subnetPrefix: String, port: Int): List<PcStatusResult> =
        coroutineScope {
            val jobs = (1..254).map { host ->
                async(Dispatchers.IO) {
                    val candidateIp = "$subnetPrefix.$host"
                    probeSingleIp(candidateIp, port, timeoutMs = 350)
                }
            }
            jobs.awaitAll().filterNotNull().filter { it.isOnline }
        }

    private fun probeSingleIp(ip: String, port: Int, timeoutMs: Int): PcStatusResult? {
        var connection: HttpURLConnection? = null
        return try {
            val url = URL("http://$ip:$port/status")
            connection = (url.openConnection() as HttpURLConnection).apply {
                requestMethod = "GET"
                connectTimeout = timeoutMs
                readTimeout = timeoutMs
            }
            if (connection.responseCode == 200) {
                val response = BufferedReader(InputStreamReader(connection.inputStream)).use {
                    it.readText()
                }
                val json = JSONObject(response)
                val host = json.optString("hostname").takeIf { it.isNotEmpty() }
                val remoteIp = json.optString("ip").ifEmpty { ip }
                val diagJson = json.optJSONObject("wolDiagnostics")
                val diag = diagJson?.let {
                    WolDiagnostics(
                        isEthernet = it.optBoolean("isEthernet", true),
                        adapterName = it.optString("adapterName", ""),
                        wakeArmed = it.optBoolean("wakeArmed", true),
                        fastStartupDisabled = it.optBoolean("fastStartupDisabled", true),
                        readyForWol = it.optBoolean("readyForWol", true)
                    )
                }
                PcStatusResult(
                    isOnline = true,
                    hostname = host,
                    macAddress = json.optString("mac").takeIf { it.isNotEmpty() }?.uppercase(),
                    ipAddress = remoteIp,
                    port = json.optInt("port", port),
                    requiresPin = json.optBoolean("requiresPin", false),
                    wolDiagnostics = diag,
                    message = "Conectado a ${host ?: "PC"} ($remoteIp)"
                )
            } else null
        } catch (_: Exception) {
            null
        } finally {
            connection?.disconnect()
        }
    }

    private fun getPhoneLocalIp(): String? {
        return try {
            val interfaces = NetworkInterface.getNetworkInterfaces()
            while (interfaces.hasMoreElements()) {
                val nic = interfaces.nextElement()
                if (!nic.isUp || nic.isLoopback) continue
                val addresses = nic.inetAddresses
                while (addresses.hasMoreElements()) {
                    val addr = addresses.nextElement()
                    if (addr is Inet4Address && !addr.isLoopbackAddress) {
                        return addr.hostAddress
                    }
                }
            }
            null
        } catch (_: Exception) {
            null
        }
    }

    /**
     * Envia o Magic Packet (Wake-on-LAN) em rajada (burst) para garantir entrega na rede local
     */
    suspend fun sendWakeOnLan(
        macAddress: String,
        ipAddress: String,
        burstCount: Int = 3
    ): ActionResult = withContext(Dispatchers.IO) {
        try {
            val macBytes = parseMacAddress(macAddress)
            val magicPacket = ByteArray(6 + 16 * macBytes.size)
            for (i in 0 until 6) {
                magicPacket[i] = 0xFF.toByte()
            }
            for (i in 6 until magicPacket.size step macBytes.size) {
                System.arraycopy(macBytes, 0, magicPacket, i, macBytes.size)
            }

            val targets = mutableSetOf("255.255.255.255")
            val localIp = getPhoneLocalIp()
            val localPrefix = localIp?.substringBeforeLast(".", "") ?: ""
            if (localPrefix.isNotEmpty()) {
                targets.add("$localPrefix.255")
            }

            val parts = ipAddress.trim().split(".")
            if (parts.size == 4) {
                targets.add("${parts[0]}.${parts[1]}.${parts[2]}.255")
                targets.add(ipAddress.trim())
            }

            DatagramSocket().use { socket ->
                socket.broadcast = true
                for (b in 1..burstCount) {
                    for (target in targets) {
                        val address = InetAddress.getByName(target)
                        for (port in listOf(9, 7)) {
                            val packet = DatagramPacket(magicPacket, magicPacket.size, address, port)
                            socket.send(packet)
                        }
                    }
                    if (b < burstCount) {
                        delay(120)
                    }
                }
            }

            ActionResult(
                success = true,
                message = "⚡ Pacote Wake-on-LAN enviado para $macAddress!"
            )
        } catch (e: IllegalArgumentException) {
            ActionResult(success = false, message = e.message ?: "MAC Address inválido.")
        } catch (e: Exception) {
            ActionResult(
                success = false,
                message = "Erro ao enviar Wake-on-LAN: ${e.localizedMessage ?: e.javaClass.simpleName}"
            )
        }
    }

    /**
     * Verifica se o PC está online. Se o IP antigo não responder (ex: roteador trocou o IP via DHCP),
     * tenta localizar automaticamente o novo IP do mesmo PC via MAC Address ou Hostname!
     */
    suspend fun checkStatus(config: PcConfig): PcStatusResult = withContext(Dispatchers.IO) {
        val ip = config.ipAddress.trim()
        if (ip.isNotEmpty()) {
            val direct = probeSingleIp(ip, config.port, timeoutMs = 1400)
            if (direct != null && direct.isOnline) {
                return@withContext direct
            }
        }

        // Auto-recuperação caso o roteador tenha mudado o IP do PC (DHCP) ou o IP esteja vazio
        val allOnline = discoverAllPcsOnNetwork(config.port)
        val matched = when {
            config.macAddress.isNotBlank() -> allOnline.firstOrNull {
                it.macAddress.equals(config.macAddress.trim(), ignoreCase = true)
            }
            config.hostname.isNotBlank() && config.hostname != "Nenhum PC pareado" -> allOnline.firstOrNull {
                it.hostname.equals(config.hostname.trim(), ignoreCase = true)
            }
            allOnline.size == 1 -> allOnline.first()
            else -> null
        }

        if (matched != null) {
            return@withContext matched.copy(
                message = "Conectado automaticamente a ${matched.hostname} (${matched.ipAddress})"
            )
        }

        PcStatusResult(
            isOnline = false,
            message = if (ip.isEmpty()) "Toque em 'Buscar PC na Rede' para parear automaticamente"
            else "PC desligado ou fora da rede ($ip)"
        )
    }

    /**
     * Envia qualquer comando de energia ao PC:
     * endpoint: /shutdown, /restart, /sleep, /hibernate, /lock, /cancel-shutdown
     */
    suspend fun sendPowerCommand(
        config: PcConfig,
        endpoint: String,
        delaySeconds: Int = 5
    ): ActionResult = withContext(Dispatchers.IO) {
        val ip = config.ipAddress.trim()
        if (ip.isEmpty()) {
            return@withContext ActionResult(false, "Toque em 'Buscar PC na Rede' primeiro.")
        }

        val cleanEndpoint = if (endpoint.startsWith("/")) endpoint else "/$endpoint"
        var connection: HttpURLConnection? = null
        try {
            val url = URL("http://$ip:${config.port}$cleanEndpoint")
            connection = (url.openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"
                connectTimeout = 3000
                readTimeout = 3000
                doOutput = true
                setRequestProperty("Content-Type", "application/json; charset=utf-8")
                setRequestProperty("X-PC-Power-Client", "1")
                if (config.pin.isNotBlank()) {
                    setRequestProperty("X-Auth-Pin", config.pin.trim())
                }
            }

            val payload = JSONObject().apply {
                put("delay", delaySeconds)
                if (config.pin.isNotBlank()) {
                    put("pin", config.pin.trim())
                }
            }

            OutputStreamWriter(connection.outputStream, Charsets.UTF_8).use { writer ->
                writer.write(payload.toString())
                writer.flush()
            }

            val code = connection.responseCode
            val stream = if (code in 200..299) connection.inputStream else connection.errorStream
            val body = stream?.let {
                BufferedReader(InputStreamReader(it)).use { reader -> reader.readText() }
            }.orEmpty()

            val json = runCatching { JSONObject(body) }.getOrNull()
            val msg = json?.optString("message")?.takeIf { it.isNotEmpty() }
                ?: if (code in 200..299) "Comando executado com sucesso!" else "Erro HTTP $code"

            ActionResult(success = code in 200..299, message = msg)
        } catch (e: Exception) {
            ActionResult(
                success = false,
                message = "Não foi possível conectar ao PC ($ip:${config.port}). Verifique se o PC está ligado e no mesmo Wi-Fi."
            )
        } finally {
            connection?.disconnect()
        }
    }

    suspend fun sendShutdownCommand(
        config: PcConfig,
        cancel: Boolean = false,
        delaySeconds: Int = 5
    ): ActionResult {
        return sendPowerCommand(
            config,
            if (cancel) "/cancel-shutdown" else "/shutdown",
            delaySeconds
        )
    }

    private fun parseMacAddress(mac: String): ByteArray {
        val clean = mac.trim().replace("-", ":").uppercase()
        val hexParts = clean.split(":")
        require(hexParts.size == 6 && hexParts.all { it.length == 2 }) {
            "Conecte ao PC ligado pelo menos uma vez ('Buscar PC na Rede') para salvar o MAC Address automaticamente."
        }
        return ByteArray(6) { i ->
            hexParts[i].toInt(16).toByte()
        }
    }
}
