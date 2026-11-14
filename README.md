# PC Power Remote (Android + Windows Agent)

Controle o seu computador (**Ligar via Wake-on-LAN** e **Desligar via Rede Local**) diretamente pelo celular Android conectado no mesmo Wi-Fi — **com descoberta automática na rede** (sem precisar digitar IP ou MAC Address manualmente).

---

## ✨ Principais Funcionalidades

- **🔍 Descoberta Automática na Rede (Zero Configuração Manual):**
  - O aplicativo Android encontra automaticamente qualquer computador rodando o agente no mesmo Wi-Fi (via *UDP Broadcast* na porta `5051` + varredura inteligente de sub-rede `/24` na porta `5050`) e preenche o **IP**, **MAC Address** e **Nome do PC** sozinho.
- **⚡ Ligar Computador (Wake-on-LAN):**
  - Envia o *Magic Packet* UDP (portas `9` e `7`) para acordar/ligar o computador mesmo quando ele está desligado.
- **⏻ Desligar Computador & Cancelar Desligamento:**
  - Envia o comando de desligamento seguro para o agente no Windows (com confirmação e opção de cancelar em até 5 segundos).
- **🔒 Segurança para Redes Locais:**
  - Suporte opcional a **PIN de Segurança** no agente Windows e no app Android.
  - Regras de Firewall restritas exclusivamente a **Redes Privadas** (`profile=private,domain`), bloqueando acessos caso o computador seja conectado a redes Wi-Fi públicas.

---

## 📂 Estrutura do Repositório

- `pc-agent/` — Agente e configurador automático para Windows:
  - [`PCPowerSetup_e_Agente.cs`](file:///c:/Users/Usuario/Downloads/Projetos/Pessoal/pc-agent/PCPowerSetup_e_Agente.cs): Código-fonte C# do executável standalone para Windows (com painel visual, ícone na bandeja do sistema, servidor HTTP `5050`, servidor de descoberta UDP `5051` e configuração automática de Wake-on-LAN, Firewall e Inicialização do Windows).
  - [`pc_power_agent.py`](file:///c:/Users/Usuario/Downloads/Projetos/Pessoal/pc-agent/pc_power_agent.py): Alternativa multiplataforma em Python puro (sem dependências externas).
- `android-app/` — Código-fonte do aplicativo Android nativo em **Kotlin + Jetpack Compose (Material 3)**:
  - [`PcPowerClient.kt`](file:///c:/Users/Usuario/Downloads/Projetos/Pessoal/android-app/app/src/main/java/com/pessoal/pcpower/network/PcPowerClient.kt): Cliente de descoberta automática na rede, envio de Magic Packet (Wake-on-LAN) e controle HTTP.
  - [`PowerRemoteScreen.kt`](file:///c:/Users/Usuario/Downloads/Projetos/Pessoal/android-app/app/src/main/java/com/pessoal/pcpower/ui/PowerRemoteScreen.kt): Interface principal em Jetpack Compose.

---

## 🚀 Como Usar (Downloads Prontos / Releases)

1. **No Computador (Windows):**
   - Execute `PCPowerSetup_e_Agente.exe` e confirme a permissão de Administrador (*Sim*).
   - Ele configurará automaticamente:
     1. Inicialização automática junto com o Windows;
     2. Regras do Firewall do Windows (redes privadas);
     3. Wake-on-LAN (Magic Packet) na placa de rede ativa;
     4. Desativação da Inicialização Rápida (*Fast Startup*) para que o Windows não bloqueie o Wake-on-LAN ao desligar.
2. **No Celular (Android):**
   - Instale o `PCPowerRemote.apk` e abra o aplicativo conectado ao mesmo Wi-Fi do PC.
   - Ele encontrará o seu computador automaticamente (ou basta tocar em **"🔍 Buscar PC na Rede Automaticamente"**).

> **Nota sobre a BIOS/UEFI (Wake-on-LAN):** Caso a sua placa-mãe venha com o Wake-on-LAN desativado de fábrica, ative a opção **Wake on LAN / Power On By PCI-E** na BIOS e deixe a opção **ErP Ready** como *Disabled*.

---

## 🛠️ Como Compilar Manualmente a partir do Código-Fonte

### Compilar o Executável Windows (`.exe`)
Sem precisar instalar nada (usando o compilador nativo do .NET Framework presente no Windows):
```powershell
& "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe" /target:winexe /out:PCPowerSetup_e_Agente.exe /r:System.dll,System.Core.dll,System.Drawing.dll,System.Windows.Forms.dll pc-agent\PCPowerSetup_e_Agente.cs
```

### Compilar o Aplicativo Android
Abra a pasta `android-app` no **Android Studio** e clique em **Run (▶)** ou execute `./gradlew assembleDebug`.

---

## 📄 Licença

Distribuído sob a licença **MIT**. Veja o arquivo [LICENSE](file:///c:/Users/Usuario/Downloads/Projetos/Pessoal/LICENSE) para mais detalhes.
