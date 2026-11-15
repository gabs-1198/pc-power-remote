package com.pessoal.pcpower.ui

import android.content.Context
import android.os.Build
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import androidx.compose.animation.animateColorAsState
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Bedtime
import androidx.compose.material.icons.filled.Computer
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.PowerSettingsNew
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.RestartAlt
import androidx.compose.material.icons.filled.Save
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.SettingsEthernet
import androidx.compose.material.icons.filled.Wifi
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import com.pessoal.pcpower.data.PcConfig
import com.pessoal.pcpower.data.PcConfigStore
import com.pessoal.pcpower.network.PcPowerClient
import com.pessoal.pcpower.network.PcStatusResult
import com.pessoal.pcpower.network.WolDiagnostics
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

private fun triggerHapticSuccess(context: Context) {
    try {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            val vibratorManager = context.getSystemService(Context.VIBRATOR_MANAGER_SERVICE) as? VibratorManager
            vibratorManager?.defaultVibrator?.vibrate(VibrationEffect.createPredefined(VibrationEffect.EFFECT_HEAVY_CLICK))
        } else {
            @Suppress("DEPRECATION")
            val vibrator = context.getSystemService(Context.VIBRATOR_SERVICE) as? Vibrator
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                vibrator?.vibrate(VibrationEffect.createPredefined(VibrationEffect.EFFECT_HEAVY_CLICK))
            } else {
                vibrator?.vibrate(150)
            }
        }
    } catch (_: Exception) { }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PowerRemoteScreen(configStore: PcConfigStore) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val snackbarHostState = remember { SnackbarHostState() }

    var savedConfig by remember { mutableStateOf(configStore.load()) }
    var savedPcs by remember { mutableStateOf(configStore.loadSavedPcs()) }

    var ipInput by remember { mutableStateOf(savedConfig.ipAddress) }
    var macInput by remember { mutableStateOf(savedConfig.macAddress) }
    var portInput by remember { mutableStateOf(savedConfig.port.toString()) }
    var pinInput by remember { mutableStateOf(savedConfig.pin) }
    var hostname by remember { mutableStateOf(savedConfig.hostname) }

    var isOnline by remember { mutableStateOf(false) }
    var isCheckingStatus by remember { mutableStateOf(false) }
    var isSearchingNetwork by remember { mutableStateOf(false) }
    var isSendingCommand by remember { mutableStateOf(false) }
    var isWakingUp by remember { mutableStateOf(false) }
    var wakingProgressSeconds by remember { mutableStateOf(0) }

    var wolDiag by remember { mutableStateOf<WolDiagnostics?>(null) }
    var showShutdownConfirm by remember { mutableStateOf(false) }
    var showRestartConfirm by remember { mutableStateOf(false) }
    var showManualFields by remember { mutableStateOf(false) }
    var shutdownDelayInput by remember { mutableStateOf("5") }
    var discoveredPcsDialog by remember { mutableStateOf<List<PcStatusResult>>(emptyList()) }
    var lastStatusMessage by remember { mutableStateOf("Procurando computador automaticamente na rede...") }

    fun currentConfig(): PcConfig {
        return PcConfig(
            hostname = hostname,
            ipAddress = ipInput.trim(),
            macAddress = macInput.trim().uppercase(),
            port = portInput.toIntOrNull() ?: 5050,
            pin = pinInput.trim()
        )
    }

    fun applyDiscoveredPc(pc: PcStatusResult) {
        isOnline = true
        pc.hostname?.let { hostname = it }
        pc.ipAddress?.let { ipInput = it }
        pc.macAddress?.let { macInput = it }
        portInput = pc.port.toString()
        wolDiag = pc.wolDiagnostics
        lastStatusMessage = "Conectado automaticamente a $hostname ($ipInput)"
        val updated = currentConfig()
        configStore.save(updated)
        savedConfig = updated
        savedPcs = configStore.loadSavedPcs()
    }

    suspend fun autoDiscoverPc(notifyUser: Boolean) {
        isSearchingNetwork = true
        lastStatusMessage = "Procurando PCs automaticamente no Wi-Fi..."
        val port = portInput.toIntOrNull() ?: 5050
        val foundList = PcPowerClient.discoverAllPcsOnNetwork(port)
        isSearchingNetwork = false

        when {
            foundList.size == 1 -> {
                applyDiscoveredPc(foundList.first())
                if (notifyUser) {
                    snackbarHostState.showSnackbar("✔ Conectado automaticamente a $hostname ($ipInput)")
                }
            }
            foundList.size > 1 -> {
                discoveredPcsDialog = foundList
            }
            else -> {
                isOnline = false
                lastStatusMessage = "Nenhum PC ligado encontrado no Wi-Fi. Abra o agente no Windows."
                if (notifyUser) {
                    snackbarHostState.showSnackbar("Nenhum PC encontrado na rede Wi-Fi.")
                }
            }
        }
    }

    suspend fun refreshStatus() {
        if (isWakingUp) return
        isCheckingStatus = true
        val cfg = currentConfig()
        val status = PcPowerClient.checkStatus(cfg)
        isOnline = status.isOnline
        lastStatusMessage = status.message
        if (status.isOnline) {
            status.hostname?.let { hostname = it }
            status.ipAddress?.let { ipInput = it }
            status.macAddress?.let { macInput = it }
            status.wolDiagnostics?.let { wolDiag = it }
            val updated = currentConfig()
            configStore.save(updated)
            savedConfig = updated
            savedPcs = configStore.loadSavedPcs()
        }
        isCheckingStatus = false
    }

    fun executeWakeOnLan() {
        scope.launch {
            val cfg = currentConfig()
            configStore.save(cfg)
            savedConfig = cfg

            isWakingUp = true
            wakingProgressSeconds = 0
            lastStatusMessage = "⚡ Enviando pacote mágico (WoL) e aguardando inicialização..."

            // Disparo redundante em rajada (burst)
            PcPowerClient.sendWakeOnLan(cfg.macAddress, cfg.ipAddress, burstCount = 3)

            val startTime = System.currentTimeMillis()
            val maxWaitMs = 45_000L
            var wokeUp = false

            while (System.currentTimeMillis() - startTime < maxWaitMs) {
                delay(1500)
                wakingProgressSeconds = ((System.currentTimeMillis() - startTime) / 1000).toInt()
                val check = PcPowerClient.checkStatus(cfg)
                if (check.isOnline) {
                    wokeUp = true
                    isOnline = true
                    check.hostname?.let { hostname = it }
                    check.wolDiagnostics?.let { wolDiag = it }
                    lastStatusMessage = "✔ Computador ligado e pronto!"
                    break
                }
            }

            isWakingUp = false
            if (wokeUp) {
                triggerHapticSuccess(context)
                snackbarHostState.showSnackbar("✔ O computador ligou com sucesso!")
                refreshStatus()
            } else {
                snackbarHostState.showSnackbar("O computador não respondeu após 45s. Verifique o cabo de rede ou a BIOS.")
            }
        }
    }

    LaunchedEffect(savedConfig.ipAddress, savedConfig.macAddress, savedConfig.port) {
        while (isActive) {
            refreshStatus()
            delay(4000)
        }
    }

    // Modal de múltiplos computadores na rede
    if (discoveredPcsDialog.isNotEmpty()) {
        AlertDialog(
            onDismissRequest = { discoveredPcsDialog = emptyList() },
            title = { Text("Escolha o Computador na Rede") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(
                        "Foram encontrados ${discoveredPcsDialog.size} computadores no seu Wi-Fi. Toque em qual deseja conectar:",
                        style = MaterialTheme.typography.bodyMedium
                    )
                    for (pc in discoveredPcsDialog) {
                        Card(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clickable {
                                    applyDiscoveredPc(pc)
                                    discoveredPcsDialog = emptyList()
                                    scope.launch {
                                        snackbarHostState.showSnackbar("✔ Conectado a ${pc.hostname}!")
                                    }
                                },
                            shape = RoundedCornerShape(12.dp)
                        ) {
                            Column(modifier = Modifier.padding(14.dp)) {
                                Text(
                                    text = pc.hostname ?: "Computador",
                                    style = MaterialTheme.typography.titleSmall,
                                    fontWeight = FontWeight.Bold
                                )
                                Text(
                                    text = "IP: ${pc.ipAddress} • MAC: ${pc.macAddress ?: "-"}",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant
                                )
                            }
                        }
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = { discoveredPcsDialog = emptyList() }) {
                    Text("Fechar")
                }
            }
        )
    }

    // Modal Desligar
    if (showShutdownConfirm) {
        AlertDialog(
            onDismissRequest = { showShutdownConfirm = false },
            title = { Text("Desligar Computador?") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("Tem certeza que deseja desligar o computador $hostname ($ipInput)?")
                    OutlinedTextField(
                        value = shutdownDelayInput,
                        onValueChange = { shutdownDelayInput = it.filter { ch -> ch.isDigit() } },
                        label = { Text("Tempo de espera (segundos)") },
                        singleLine = true,
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                        modifier = Modifier.fillMaxWidth()
                    )
                }
            },
            confirmButton = {
                Button(
                    colors = ButtonDefaults.buttonColors(
                        containerColor = Color(0xFFD32F2F),
                        contentColor = Color.White
                    ),
                    onClick = {
                        showShutdownConfirm = false
                        scope.launch {
                            isSendingCommand = true
                            val delaySec = shutdownDelayInput.toIntOrNull() ?: 5
                            val cfg = currentConfig()
                            configStore.save(cfg)
                            val result = PcPowerClient.sendShutdownCommand(cfg, cancel = false, delaySeconds = delaySec)
                            isSendingCommand = false
                            snackbarHostState.showSnackbar(result.message)
                            delay(1500)
                            refreshStatus()
                        }
                    }
                ) {
                    Text("Sim, Desligar")
                }
            },
            dismissButton = {
                TextButton(onClick = { showShutdownConfirm = false }) {
                    Text("Cancelar")
                }
            }
        )
    }

    // Modal Reiniciar
    if (showRestartConfirm) {
        AlertDialog(
            onDismissRequest = { showRestartConfirm = false },
            title = { Text("Reiniciar Computador?") },
            text = {
                Text("Deseja reiniciar $hostname ($ipInput) agora?")
            },
            confirmButton = {
                Button(
                    colors = ButtonDefaults.buttonColors(
                        containerColor = Color(0xFFEF6C00),
                        contentColor = Color.White
                    ),
                    onClick = {
                        showRestartConfirm = false
                        scope.launch {
                            isSendingCommand = true
                            val cfg = currentConfig()
                            val result = PcPowerClient.sendPowerCommand(cfg, "/restart", delaySeconds = 5)
                            isSendingCommand = false
                            snackbarHostState.showSnackbar(result.message)
                            delay(1500)
                            refreshStatus()
                        }
                    }
                ) {
                    Text("Reiniciar")
                }
            },
            dismissButton = {
                TextButton(onClick = { showRestartConfirm = false }) {
                    Text("Cancelar")
                }
            }
        )
    }

    Scaffold(
        snackbarHost = { SnackbarHost(snackbarHostState) },
        topBar = {
            TopAppBar(
                title = {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(
                            imageVector = Icons.Default.Computer,
                            contentDescription = null,
                            modifier = Modifier.size(26.dp)
                        )
                        Spacer(modifier = Modifier.width(10.dp))
                        Column {
                            Text(
                                text = "PC Power Remote",
                                style = MaterialTheme.typography.titleMedium,
                                fontWeight = FontWeight.Bold
                            )
                            Text(
                                text = hostname,
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                    }
                },
                actions = {
                    IconButton(
                        onClick = {
                            scope.launch {
                                autoDiscoverPc(notifyUser = true)
                            }
                        }
                    ) {
                        if (isCheckingStatus || isSearchingNetwork) {
                            CircularProgressIndicator(
                                modifier = Modifier.size(20.dp),
                                strokeWidth = 2.dp
                            )
                        } else {
                            Icon(
                                imageVector = Icons.Default.Refresh,
                                contentDescription = "Buscar na Rede"
                            )
                        }
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.surface
                )
            )
        }
    ) { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            // Seletor rápido de PCs pareados
            if (savedPcs.size > 1) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    for (pc in savedPcs) {
                        val isSelected = pc.macAddress.equals(macInput, ignoreCase = true) ||
                            (pc.ipAddress.isNotEmpty() && pc.ipAddress == ipInput)
                        FilterChip(
                            selected = isSelected,
                            onClick = {
                                hostname = pc.hostname
                                ipInput = pc.ipAddress
                                macInput = pc.macAddress
                                portInput = pc.port.toString()
                                pinInput = pc.pin
                                configStore.save(pc)
                                savedConfig = pc
                                scope.launch { refreshStatus() }
                            },
                            label = { Text(pc.hostname) }
                        )
                    }
                }
            }

            // Card Principal
            Card(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(20.dp),
                colors = CardDefaults.cardColors(
                    containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.55f)
                )
            ) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(20.dp),
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    val statusColor by animateColorAsState(
                        targetValue = when {
                            isWakingUp -> Color(0xFFF57C00)
                            isOnline -> Color(0xFF2E7D32)
                            else -> Color(0xFF757575)
                        },
                        label = "statusColor"
                    )

                    Surface(
                        color = statusColor.copy(alpha = 0.16f),
                        shape = RoundedCornerShape(50),
                        modifier = Modifier.padding(bottom = 12.dp)
                    ) {
                        Row(
                            modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            if (isWakingUp) {
                                CircularProgressIndicator(
                                    modifier = Modifier.size(12.dp),
                                    strokeWidth = 2.dp,
                                    color = statusColor
                                )
                            } else {
                                Box(
                                    modifier = Modifier
                                        .size(10.dp)
                                        .clip(CircleShape)
                                        .background(statusColor)
                                )
                            }
                            Spacer(modifier = Modifier.width(8.dp))
                            Text(
                                text = when {
                                    isWakingUp -> "INICIALIZANDO PC (${wakingProgressSeconds}s)..."
                                    isOnline -> "COMPUTADOR LIGADO"
                                    else -> "COMPUTADOR DESLIGADO"
                                },
                                color = statusColor,
                                style = MaterialTheme.typography.labelLarge,
                                fontWeight = FontWeight.Bold
                            )
                        }
                    }

                    Text(
                        text = lastStatusMessage,
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )

                    // Selo de Diagnóstico WoL
                    if (wolDiag != null) {
                        Spacer(modifier = Modifier.height(10.dp))
                        val isEth = wolDiag?.isEthernet == true
                        val ready = wolDiag?.readyForWol == true
                        Surface(
                            color = if (ready) Color(0xFF1B5E20).copy(alpha = 0.2f) else Color(0xFFE65100).copy(alpha = 0.2f),
                            shape = RoundedCornerShape(8.dp)
                        ) {
                            Text(
                                text = if (ready) "🟢 Diagnóstico WoL: Pronto via Cabo Ethernet"
                                else if (!isEth) "🟡 Diagnóstico WoL: PC em Wi-Fi (WoL pode falhar com PC desligado)"
                                else "🔴 Diagnóstico WoL: Placa não autorizada a acordar",
                                color = if (ready) Color(0xFF81C784) else Color(0xFFFFB74D),
                                style = MaterialTheme.typography.bodySmall,
                                modifier = Modifier.padding(horizontal = 10.dp, vertical = 5.dp)
                            )
                        }
                    }

                    Spacer(modifier = Modifier.height(20.dp))

                    // Botão Ligar (WoL) com confirmação e animação
                    Button(
                        onClick = { executeWakeOnLan() },
                        enabled = !isSendingCommand && !isWakingUp,
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(58.dp),
                        shape = RoundedCornerShape(14.dp),
                        colors = ButtonDefaults.buttonColors(
                            containerColor = Color(0xFF2E7D32),
                            contentColor = Color.White
                        )
                    ) {
                        if (isWakingUp) {
                            CircularProgressIndicator(
                                modifier = Modifier.size(24.dp),
                                color = Color.White,
                                strokeWidth = 2.dp
                            )
                            Spacer(modifier = Modifier.width(10.dp))
                            Text(
                                text = "AGUARDANDO DESPERTAR...",
                                style = MaterialTheme.typography.titleSmall,
                                fontWeight = FontWeight.Bold
                            )
                        } else {
                            Icon(
                                imageVector = Icons.Default.PowerSettingsNew,
                                contentDescription = null,
                                modifier = Modifier.size(24.dp)
                            )
                            Spacer(modifier = Modifier.width(10.dp))
                            Text(
                                text = "LIGAR COMPUTADOR (Wake-on-LAN)",
                                style = MaterialTheme.typography.titleSmall,
                                fontWeight = FontWeight.Bold
                            )
                        }
                    }

                    Spacer(modifier = Modifier.height(12.dp))

                    // Botão Desligar
                    Button(
                        onClick = { showShutdownConfirm = true },
                        enabled = !isSendingCommand && !isWakingUp,
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(58.dp),
                        shape = RoundedCornerShape(14.dp),
                        colors = ButtonDefaults.buttonColors(
                            containerColor = Color(0xFFC62828),
                            contentColor = Color.White
                        )
                    ) {
                        Icon(
                            imageVector = Icons.Default.PowerSettingsNew,
                            contentDescription = null,
                            modifier = Modifier.size(24.dp)
                        )
                        Spacer(modifier = Modifier.width(10.dp))
                        Text(
                            text = "DESLIGAR COMPUTADOR",
                            style = MaterialTheme.typography.titleSmall,
                            fontWeight = FontWeight.Bold
                        )
                    }

                    Spacer(modifier = Modifier.height(14.dp))

                    // Novas Ações de Energia: Suspender, Reiniciar, Bloquear
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        FilledTonalButton(
                            onClick = {
                                scope.launch {
                                    isSendingCommand = true
                                    val res = PcPowerClient.sendPowerCommand(currentConfig(), "/sleep")
                                    isSendingCommand = false
                                    snackbarHostState.showSnackbar(res.message)
                                    delay(2000)
                                    refreshStatus()
                                }
                            },
                            enabled = !isSendingCommand && isOnline,
                            modifier = Modifier.weight(1f),
                            shape = RoundedCornerShape(10.dp)
                        ) {
                            Icon(Icons.Default.Bedtime, contentDescription = null, modifier = Modifier.size(16.dp))
                            Spacer(modifier = Modifier.width(4.dp))
                            Text("Dormir", style = MaterialTheme.typography.labelMedium)
                        }

                        FilledTonalButton(
                            onClick = { showRestartConfirm = true },
                            enabled = !isSendingCommand && isOnline,
                            modifier = Modifier.weight(1f),
                            shape = RoundedCornerShape(10.dp)
                        ) {
                            Icon(Icons.Default.RestartAlt, contentDescription = null, modifier = Modifier.size(16.dp))
                            Spacer(modifier = Modifier.width(4.dp))
                            Text("Reiniciar", style = MaterialTheme.typography.labelMedium)
                        }

                        FilledTonalButton(
                            onClick = {
                                scope.launch {
                                    val res = PcPowerClient.sendPowerCommand(currentConfig(), "/lock")
                                    snackbarHostState.showSnackbar(res.message)
                                }
                            },
                            enabled = !isSendingCommand && isOnline,
                            modifier = Modifier.weight(1f),
                            shape = RoundedCornerShape(10.dp)
                        ) {
                            Icon(Icons.Default.Lock, contentDescription = null, modifier = Modifier.size(16.dp))
                            Spacer(modifier = Modifier.width(4.dp))
                            Text("Bloquear", style = MaterialTheme.typography.labelMedium)
                        }
                    }

                    Spacer(modifier = Modifier.height(8.dp))

                    OutlinedButton(
                        onClick = {
                            scope.launch {
                                val result = PcPowerClient.sendShutdownCommand(
                                    currentConfig(),
                                    cancel = true
                                )
                                snackbarHostState.showSnackbar(result.message)
                            }
                        },
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(12.dp)
                    ) {
                        Text("Cancelar Desligamento / Reinício")
                    }
                }
            }

            // Card Descoberta e Configuração
            Card(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(20.dp)
            ) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(20.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(
                            imageVector = Icons.Default.Wifi,
                            contentDescription = null,
                            tint = MaterialTheme.colorScheme.primary
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            text = "Descoberta Automática na Rede",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.SemiBold
                        )
                    }

                    Button(
                        onClick = {
                            scope.launch {
                                autoDiscoverPc(notifyUser = true)
                            }
                        },
                        enabled = !isSearchingNetwork,
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(52.dp),
                        shape = RoundedCornerShape(12.dp)
                    ) {
                        Icon(
                            imageVector = Icons.Default.Search,
                            contentDescription = null,
                            modifier = Modifier.size(20.dp)
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            text = if (isSearchingNetwork) "Buscando PCs no Wi-Fi..." else "Buscar PC na Rede Automaticamente",
                            fontWeight = FontWeight.Bold
                        )
                    }

                    if (ipInput.isNotEmpty() || macInput.isNotEmpty()) {
                        Text(
                            text = "PC pareado: $hostname • IP: ${ipInput.ifEmpty { "-" }} • MAC: ${macInput.ifEmpty { "-" }}",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }

                    TextButton(
                        onClick = { showManualFields = !showManualFields },
                        modifier = Modifier.align(Alignment.End)
                    ) {
                        Text(
                            if (showManualFields) "Ocultar Opções Avançadas / PIN"
                            else "Configurar PIN ou Editar Manualmente"
                        )
                    }

                    if (showManualFields) {
                        OutlinedTextField(
                            value = pinInput,
                            onValueChange = { pinInput = it },
                            label = { Text("PIN de Segurança (se configurado no PC)") },
                            singleLine = true,
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
                            modifier = Modifier.fillMaxWidth()
                        )

                        OutlinedTextField(
                            value = ipInput,
                            onValueChange = { ipInput = it },
                            label = { Text("Endereço IP (preenchido automaticamente)") },
                            singleLine = true,
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri),
                            modifier = Modifier.fillMaxWidth()
                        )

                        OutlinedTextField(
                            value = macInput,
                            onValueChange = { macInput = it.uppercase() },
                            label = { Text("MAC Address (preenchido automaticamente)") },
                            singleLine = true,
                            keyboardOptions = KeyboardOptions(
                                capitalization = KeyboardCapitalization.Characters
                            ),
                            leadingIcon = {
                                Icon(
                                    imageVector = Icons.Default.SettingsEthernet,
                                    contentDescription = null
                                )
                            },
                            modifier = Modifier.fillMaxWidth()
                        )

                        OutlinedTextField(
                            value = portInput,
                            onValueChange = { portInput = it.filter { ch -> ch.isDigit() } },
                            label = { Text("Porta HTTP") },
                            singleLine = true,
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                            modifier = Modifier.fillMaxWidth()
                        )

                        Button(
                            onClick = {
                                val updated = currentConfig()
                                configStore.save(updated)
                                savedConfig = updated
                                savedPcs = configStore.loadSavedPcs()
                                scope.launch {
                                    refreshStatus()
                                    snackbarHostState.showSnackbar("Configurações salvas!")
                                }
                            },
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Icon(
                                imageVector = Icons.Default.Save,
                                contentDescription = null,
                                modifier = Modifier.size(18.dp)
                            )
                            Spacer(modifier = Modifier.width(6.dp))
                            Text("Salvar Alterações")
                        }
                    }
                }
            }
        }
    }
}
