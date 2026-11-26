using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.NetworkInformation;
using System.Net.Sockets;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Security.Principal;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using System.Windows.Forms;
using Microsoft.Win32;

[assembly: AssemblyTitle("PC Power Remote - Instalador e Agente")]
[assembly: AssemblyDescription("Configurador automatico de Wake-on-LAN, Descoberta na Rede e Agente de Desligamento Remoto")]
[assembly: AssemblyCompany("PC Power Remote")]
[assembly: AssemblyProduct("PC Power Remote")]
[assembly: AssemblyVersion("1.2.0.0")]

namespace PCPowerRemote
{
    static class NativeMethods
    {
        [DllImport("PowrProf.dll", SetLastError = true)]
        public static extern bool SetSuspendState(bool hibernate, bool forceCritical, bool disableWakeEvent);

        [DllImport("user32.dll", SetLastError = true)]
        public static extern bool LockWorkStation();
    }

    static class Program
    {
        private static Mutex appMutex;

        [STAThread]
        static void Main(string[] args)
        {
            bool backgroundMode = args != null && args.Any(a => a.Equals("--background", StringComparison.OrdinalIgnoreCase));
            bool elevatedRetry = args != null && args.Any(a => a.Equals("--elevated", StringComparison.OrdinalIgnoreCase));

            if (!backgroundMode && !IsAdministrator() && !elevatedRetry)
            {
                try
                {
                    ProcessStartInfo psi = new ProcessStartInfo
                    {
                        FileName = Application.ExecutablePath,
                        Arguments = "--elevated",
                        UseShellExecute = true,
                        Verb = "runas"
                    };
                    Process.Start(psi);
                    return;
                }
                catch
                {
                    // Continua mesmo se o usuario cancelar o UAC
                }
            }

            bool createdNew;
            appMutex = new Mutex(true, "Global\\PCPowerRemoteAgentMutex", out createdNew);
            if (!createdNew && backgroundMode)
            {
                return;
            }

            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new MainForm(backgroundMode));
        }

        public static bool IsAdministrator()
        {
            try
            {
                using (WindowsIdentity identity = WindowsIdentity.GetCurrent())
                {
                    WindowsPrincipal principal = new WindowsPrincipal(identity);
                    return principal.IsInRole(WindowsBuiltInRole.Administrator);
                }
            }
            catch
            {
                return false;
            }
        }
    }

    public class MainForm : Form
    {
        private const int HTTP_PORT = 5050;
        private const int DISCOVERY_UDP_PORT = 5051;
        private const string REG_SETTINGS_KEY = @"Software\PCPowerRemote";

        private TcpListener tcpListener;
        private UdpClient udpDiscoveryListener;
        private Thread serverThread;
        private Thread udpThread;
        private volatile bool isRunning = false;

        // Rate limiting de tentativas de PIN
        private readonly Dictionary<string, int> failedAttempts = new Dictionary<string, int>();
        private readonly Dictionary<string, DateTime> blockedIps = new Dictionary<string, DateTime>();
        private readonly object securityLock = new object();

        private NotifyIcon trayIcon;
        private ContextMenuStrip trayMenu;

        private Label lblStatusBadge;
        private TextBox txtIp;
        private TextBox txtMac;
        private TextBox txtHost;
        private TextBox txtPin;
        private TextBox txtLog;
        private Button btnReconfigure;

        private string currentIp = "";
        private string currentMac = "";
        private string currentHost = Environment.MachineName;
        private string currentPin = "";
        private string activeAdapterDescription = "";
        private bool isEthernetAdapter = false;

        private bool startMinimized;

        public MainForm(bool backgroundMode)
        {
            this.startMinimized = backgroundMode;
            LoadPinSetting();
            DetectNetworkInfo();
            InitializeGui();
            InitializeTray();

            this.Load += (s, e) =>
            {
                StartHttpServer();
                StartUdpDiscoveryServer();
                ThreadPool.QueueUserWorkItem(_ => RunFullSetup());

                if (startMinimized)
                {
                    this.WindowState = FormWindowState.Minimized;
                    this.ShowInTaskbar = false;
                    this.Hide();
                }
            };
        }

        private void LoadPinSetting()
        {
            try
            {
                using (RegistryKey key = Registry.CurrentUser.CreateSubKey(REG_SETTINGS_KEY))
                {
                    if (key != null)
                    {
                        currentPin = Convert.ToString(key.GetValue("PinCode", "")).Trim();
                    }
                }
            }
            catch { }
        }

        private void SavePinSetting(string pin)
        {
            currentPin = (pin ?? "").Trim();
            try
            {
                using (RegistryKey key = Registry.CurrentUser.CreateSubKey(REG_SETTINGS_KEY))
                {
                    if (key != null)
                    {
                        key.SetValue("PinCode", currentPin, RegistryValueKind.String);
                    }
                }
            }
            catch { }
        }

        private void DetectNetworkInfo()
        {
            try
            {
                using (Socket socket = new Socket(AddressFamily.InterNetwork, SocketType.Dgram, 0))
                {
                    socket.Connect("8.8.8.8", 65530);
                    IPEndPoint endPoint = socket.LocalEndPoint as IPEndPoint;
                    if (endPoint != null)
                    {
                        currentIp = endPoint.Address.ToString();
                    }
                }
            }
            catch
            {
                currentIp = "127.0.0.1";
            }

            try
            {
                foreach (NetworkInterface nic in NetworkInterface.GetAllNetworkInterfaces())
                {
                    if (nic.OperationalStatus != OperationalStatus.Up) continue;
                    if (nic.NetworkInterfaceType == NetworkInterfaceType.Loopback) continue;

                    IPInterfaceProperties ipProps = nic.GetIPProperties();
                    foreach (UnicastIPAddressInformation uni in ipProps.UnicastAddresses)
                    {
                        if (uni.Address.AddressFamily == AddressFamily.InterNetwork)
                        {
                            string ipStr = uni.Address.ToString();
                            if (ipStr == currentIp || string.IsNullOrEmpty(currentMac))
                            {
                                currentIp = ipStr;
                                byte[] macBytes = nic.GetPhysicalAddress().GetAddressBytes();
                                if (macBytes.Length == 6)
                                {
                                    currentMac = string.Join(":", macBytes.Select(b => b.ToString("X2")));
                                    activeAdapterDescription = nic.Description;
                                    isEthernetAdapter = (nic.NetworkInterfaceType == NetworkInterfaceType.Ethernet ||
                                                         nic.NetworkInterfaceType == NetworkInterfaceType.GigabitEthernet ||
                                                         nic.NetworkInterfaceType == NetworkInterfaceType.FastEthernetFx ||
                                                         nic.NetworkInterfaceType == NetworkInterfaceType.FastEthernetT);
                                }
                            }
                        }
                    }
                }
            }
            catch { }
        }

        private bool IsFastStartupDisabled()
        {
            try
            {
                using (RegistryKey powerKey = Registry.LocalMachine.OpenSubKey(@"SYSTEM\CurrentControlSet\Control\Session Manager\Power", false))
                {
                    if (powerKey != null)
                    {
                        object val = powerKey.GetValue("HiberbootEnabled");
                        if (val != null)
                        {
                            return Convert.ToInt32(val) == 0;
                        }
                    }
                }
            }
            catch { }
            return true;
        }

        private bool IsWakeArmed()
        {
            if (string.IsNullOrEmpty(activeAdapterDescription)) return true;
            try
            {
                ProcessStartInfo psi = new ProcessStartInfo
                {
                    FileName = "powercfg",
                    Arguments = "/devicequery wake_armed",
                    CreateNoWindow = true,
                    UseShellExecute = false,
                    RedirectStandardOutput = true
                };
                using (Process p = Process.Start(psi))
                {
                    if (p != null)
                    {
                        string output = p.StandardOutput.ReadToEnd();
                        p.WaitForExit(3000);
                        if (!string.IsNullOrEmpty(output) && output.IndexOf(activeAdapterDescription, StringComparison.OrdinalIgnoreCase) >= 0)
                        {
                            return true;
                        }
                    }
                }
            }
            catch { }
            return false;
        }

        private void InitializeGui()
        {
            this.Text = "PC Power Remote - Configurador & Agente Windows";
            this.Size = new Size(560, 610);
            this.MinimumSize = new Size(540, 580);
            this.StartPosition = FormStartPosition.CenterScreen;
            this.BackColor = Color.FromArgb(24, 26, 32);
            this.ForeColor = Color.White;
            this.Font = new Font("Segoe UI", 9.5f, FontStyle.Regular);
            this.Icon = SystemIcons.Shield;

            Panel headerPanel = new Panel
            {
                Dock = DockStyle.Top,
                Height = 68,
                BackColor = Color.FromArgb(32, 36, 44),
                Padding = new Padding(18, 12, 18, 12)
            };

            Label lblTitle = new Label
            {
                Text = "PC Power Remote — Agente & Descoberta Automática",
                Font = new Font("Segoe UI", 12.5f, FontStyle.Bold),
                ForeColor = Color.White,
                AutoSize = true,
                Location = new Point(18, 12)
            };

            lblStatusBadge = new Label
            {
                Text = "● ATIVO NA REDE LOCAL (HTTP 5050 | UDP 5051)",
                Font = new Font("Segoe UI", 9f, FontStyle.Bold),
                ForeColor = Color.FromArgb(76, 175, 80),
                AutoSize = true,
                Location = new Point(20, 40)
            };

            headerPanel.Controls.Add(lblTitle);
            headerPanel.Controls.Add(lblStatusBadge);

            Panel infoCard = new Panel
            {
                Location = new Point(18, 82),
                Size = new Size(508, 172),
                BackColor = Color.FromArgb(35, 39, 48),
                Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right
            };

            Label lblInfoHeader = new Label
            {
                Text = "Dados deste PC (descobertos automaticamente pelo celular no Wi-Fi):",
                Font = new Font("Segoe UI", 9.5f, FontStyle.Bold),
                ForeColor = Color.FromArgb(180, 190, 210),
                AutoSize = true,
                Location = new Point(14, 10)
            };

            Label lblIpTitle = new Label { Text = "IP Local:", Location = new Point(14, 42), AutoSize = true, ForeColor = Color.LightGray };
            txtIp = CreateReadOnlyBox(currentIp, new Point(110, 39), 140);

            Label lblPortTitle = new Label { Text = "Porta:", Location = new Point(270, 42), AutoSize = true, ForeColor = Color.LightGray };
            TextBox txtPort = CreateReadOnlyBox(HTTP_PORT.ToString(), new Point(325, 39), 70);

            Label lblMacTitle = new Label { Text = "MAC Address:", Location = new Point(14, 74), AutoSize = true, ForeColor = Color.LightGray };
            txtMac = CreateReadOnlyBox(currentMac, new Point(110, 71), 180);

            Label lblHostTitle = new Label { Text = "Nome do PC:", Location = new Point(14, 104), AutoSize = true, ForeColor = Color.LightGray };
            txtHost = CreateReadOnlyBox(currentHost, new Point(110, 101), 285);

            Label lblPinTitle = new Label { Text = "PIN Segurança:", Location = new Point(14, 136), AutoSize = true, ForeColor = Color.LightGray };
            txtPin = new TextBox
            {
                Text = currentPin,
                Location = new Point(110, 133),
                Width = 180,
                BackColor = Color.FromArgb(20, 23, 29),
                ForeColor = Color.White,
                Font = new Font("Consolas", 10f, FontStyle.Bold),
                BorderStyle = BorderStyle.FixedSingle
            };

            Button btnSavePin = new Button
            {
                Text = "Salvar PIN",
                Location = new Point(300, 131),
                Size = new Size(95, 27),
                FlatStyle = FlatStyle.Flat,
                BackColor = Color.FromArgb(55, 75, 110),
                ForeColor = Color.White,
                Cursor = Cursors.Hand
            };
            btnSavePin.FlatAppearance.BorderSize = 0;
            btnSavePin.Click += (s, e) =>
            {
                SavePinSetting(txtPin.Text);
                AppendLog(string.IsNullOrEmpty(currentPin)
                    ? "🔓 PIN removido (acesso livre na rede privada)."
                    : "🔒 PIN de segurança salvo e ativado!");
                MessageBox.Show(
                    string.IsNullOrEmpty(currentPin)
                        ? "PIN desativado. Qualquer aparelho com o app no seu Wi-Fi poderá controlar o PC."
                        : "PIN salvo com sucesso! Digite o mesmo PIN no aplicativo Android.",
                    "PC Power Remote",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Information
                );
            };

            Button btnCopy = new Button
            {
                Text = "Copiar Dados",
                Location = new Point(405, 70),
                Size = new Size(90, 88),
                FlatStyle = FlatStyle.Flat,
                BackColor = Color.FromArgb(45, 110, 210),
                ForeColor = Color.White,
                Cursor = Cursors.Hand
            };
            btnCopy.FlatAppearance.BorderSize = 0;
            btnCopy.Click += (s, e) =>
            {
                Clipboard.SetText(string.Format("IP: {0}\r\nMAC: {1}\r\nPorta: {2}\r\nHostname: {3}", currentIp, currentMac, HTTP_PORT, currentHost));
                MessageBox.Show("Dados copiados para a área de transferência!", "PC Power Remote", MessageBoxButtons.OK, MessageBoxIcon.Information);
            };

            infoCard.Controls.AddRange(new Control[] {
                lblInfoHeader, lblIpTitle, txtIp, lblPortTitle, txtPort,
                lblMacTitle, txtMac, lblHostTitle, txtHost,
                lblPinTitle, txtPin, btnSavePin, btnCopy
            });

            Label lblLogTitle = new Label
            {
                Text = "Progresso da Configuração Automática do Windows:",
                Font = new Font("Segoe UI", 9.5f, FontStyle.Bold),
                ForeColor = Color.FromArgb(180, 190, 210),
                Location = new Point(18, 266),
                AutoSize = true
            };

            txtLog = new TextBox
            {
                Location = new Point(18, 290),
                Size = new Size(508, 205),
                Multiline = true,
                ReadOnly = true,
                ScrollBars = ScrollBars.Vertical,
                BackColor = Color.FromArgb(16, 18, 22),
                ForeColor = Color.FromArgb(215, 225, 235),
                Font = new Font("Consolas", 9.2f),
                BorderStyle = BorderStyle.FixedSingle,
                Anchor = AnchorStyles.Top | AnchorStyles.Bottom | AnchorStyles.Left | AnchorStyles.Right
            };

            btnReconfigure = new Button
            {
                Text = "Reexecutar Configuração Automática",
                Location = new Point(18, 510),
                Size = new Size(255, 42),
                FlatStyle = FlatStyle.Flat,
                BackColor = Color.FromArgb(46, 125, 50),
                ForeColor = Color.White,
                Font = new Font("Segoe UI", 9.5f, FontStyle.Bold),
                Cursor = Cursors.Hand,
                Anchor = AnchorStyles.Bottom | AnchorStyles.Left
            };
            btnReconfigure.FlatAppearance.BorderSize = 0;
            btnReconfigure.Click += (s, e) =>
            {
                if (!Program.IsAdministrator())
                {
                    try
                    {
                        Process.Start(new ProcessStartInfo
                        {
                            FileName = Application.ExecutablePath,
                            Arguments = "--elevated",
                            UseShellExecute = true,
                            Verb = "runas"
                        });
                        Application.Exit();
                        return;
                    }
                    catch { }
                }
                ThreadPool.QueueUserWorkItem(_ => RunFullSetup());
            };

            Button btnMinimizeTray = new Button
            {
                Text = "Minimizar para Bandeja do Relógio",
                Location = new Point(285, 510),
                Size = new Size(241, 42),
                FlatStyle = FlatStyle.Flat,
                BackColor = Color.FromArgb(55, 62, 76),
                ForeColor = Color.White,
                Font = new Font("Segoe UI", 9.5f, FontStyle.Regular),
                Cursor = Cursors.Hand,
                Anchor = AnchorStyles.Bottom | AnchorStyles.Right
            };
            btnMinimizeTray.FlatAppearance.BorderSize = 0;
            btnMinimizeTray.Click += (s, e) => HideToTray();

            this.Controls.Add(headerPanel);
            this.Controls.Add(infoCard);
            this.Controls.Add(lblLogTitle);
            this.Controls.Add(txtLog);
            this.Controls.Add(btnReconfigure);
            this.Controls.Add(btnMinimizeTray);

            this.FormClosing += (s, e) =>
            {
                if (e.CloseReason == CloseReason.UserClosing)
                {
                    e.Cancel = true;
                    HideToTray();
                }
            };
        }

        private TextBox CreateReadOnlyBox(string value, Point location, int width)
        {
            return new TextBox
            {
                Text = value,
                ReadOnly = true,
                Location = location,
                Width = width,
                BackColor = Color.FromArgb(24, 27, 34),
                ForeColor = Color.FromArgb(100, 210, 255),
                Font = new Font("Consolas", 10f, FontStyle.Bold),
                BorderStyle = BorderStyle.FixedSingle
            };
        }

        private void InitializeTray()
        {
            trayMenu = new ContextMenuStrip();
            trayMenu.Items.Add("Abrir Painel PC Power Remote", null, (s, e) => ShowFromTray());
            trayMenu.Items.Add(new ToolStripSeparator());
            trayMenu.Items.Add("Encerrar Agente", null, (s, e) =>
            {
                isRunning = false;
                try { if (tcpListener != null) tcpListener.Stop(); } catch { }
                try { if (udpDiscoveryListener != null) udpDiscoveryListener.Close(); } catch { }
                trayIcon.Visible = false;
                Environment.Exit(0);
            });

            trayIcon = new NotifyIcon
            {
                Icon = SystemIcons.Shield,
                Text = string.Format("PC Power Remote ({0}:{1})", currentIp, HTTP_PORT),
                ContextMenuStrip = trayMenu,
                Visible = true
            };
            trayIcon.DoubleClick += (s, e) => ShowFromTray();
        }

        private void HideToTray()
        {
            this.Hide();
            this.ShowInTaskbar = false;
            trayIcon.ShowBalloonTip(
                2500,
                "PC Power Remote Ativo",
                string.Format("O agente continua rodando em segundo plano ({0}:{1}).", currentIp, HTTP_PORT),
                ToolTipIcon.Info
            );
        }

        private void ShowFromTray()
        {
            this.Show();
            this.WindowState = FormWindowState.Normal;
            this.ShowInTaskbar = true;
            this.Activate();
        }

        private void AppendLog(string text)
        {
            if (this.IsDisposed) return;
            if (txtLog.InvokeRequired)
            {
                txtLog.BeginInvoke(new Action<string>(AppendLog), text);
                return;
            }
            txtLog.AppendText(string.Format("[{0:HH:mm:ss}] {1}\r\n", DateTime.Now, text));
        }

        private void RunFullSetup()
        {
            AppendLog("Iniciando verificação e configuração automática do Windows...");
            bool isAdmin = Program.IsAdministrator();
            AppendLog(isAdmin
                ? "✔ Executando com privilégios de Administrador."
                : "⚠ Executando sem Administrador (algumas opções de Firewall/Rede requerem Admin).");

            // 1. Instalar copia persistente em %LOCALAPPDATA%\PCPowerRemote e registrar no Startup do Windows
            try
            {
                string installDir = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "PCPowerRemote");
                Directory.CreateDirectory(installDir);
                string targetExe = Path.Combine(installDir, "PCPowerAgent.exe");
                string currentExe = Application.ExecutablePath;

                if (!string.Equals(Path.GetFullPath(currentExe), Path.GetFullPath(targetExe), StringComparison.OrdinalIgnoreCase))
                {
                    File.Copy(currentExe, targetExe, true);
                }

                using (RegistryKey runKey = Registry.CurrentUser.OpenSubKey(@"Software\Microsoft\Windows\CurrentVersion\Run", true))
                {
                    if (runKey != null)
                    {
                        runKey.SetValue("PCPowerRemoteAgent", "\"" + targetExe + "\" --background");
                    }
                }
                AppendLog("✔ [1/4] Agente instalado na Inicialização Automática do Windows.");
            }
            catch (Exception ex)
            {
                AppendLog("✖ [1/4] Erro ao configurar inicialização: " + ex.Message);
            }

            // 2. Configurar Firewall do Windows (Apenas redes Privadas/Domínio para segurança em Wi-Fi público)
            if (isAdmin)
            {
                try
                {
                    RunHiddenCommand("netsh", "advfirewall firewall delete rule name=\"PC Power Remote (HTTP 5050)\"");
                    RunHiddenCommand("netsh", "advfirewall firewall add rule name=\"PC Power Remote (HTTP 5050)\" dir=in action=allow protocol=TCP localport=5050 profile=private,domain");
                    RunHiddenCommand("netsh", "advfirewall firewall delete rule name=\"PC Power Remote (WoL & Discovery UDP)\"");
                    RunHiddenCommand("netsh", "advfirewall firewall add rule name=\"PC Power Remote (WoL & Discovery UDP)\" dir=in action=allow protocol=UDP localport=7,9,5051 profile=private,domain");
                    AppendLog("✔ [2/4] Portas TCP 5050 e UDP 7/9/5051 liberadas no Firewall (Redes Privadas).");
                }
                catch (Exception ex)
                {
                    AppendLog("✖ [2/4] Erro ao liberar Firewall: " + ex.Message);
                }
            }
            else
            {
                AppendLog("⚠ [2/4] Firewall: clique em 'Reexecutar Configuração' para liberar como Admin.");
            }

            // 3. Habilitar Wake-on-LAN na Placa de Rede
            if (isAdmin)
            {
                try
                {
                    if (!string.IsNullOrEmpty(activeAdapterDescription))
                    {
                        RunHiddenCommand("powercfg", "/deviceenablewake \"" + activeAdapterDescription + "\"");
                    }

                    string psCmd = "Get-NetAdapter | Where-Object {$_.Status -eq 'Up'} | ForEach-Object { " +
                                   "Enable-NetAdapterPowerManagement -Name $_.Name -WakeOnMagicPacket -ErrorAction SilentlyContinue; " +
                                   "Set-NetAdapterAdvancedProperty -Name $_.Name -RegistryKeyword '*WakeOnMagicPacket' -RegistryValue 1 -ErrorAction SilentlyContinue " +
                                   "}";
                    RunHiddenCommand("powershell", "-NoProfile -ExecutionPolicy Bypass -Command \"" + psCmd + "\"");

                    EnableWolInRegistry();
                    AppendLog("✔ [3/4] Wake-on-LAN (Magic Packet) ativado na placa de rede (" + activeAdapterDescription + ").");
                }
                catch (Exception ex)
                {
                    AppendLog("⚠ [3/4] Aviso ao configurar placa de rede: " + ex.Message);
                }
            }
            else
            {
                AppendLog("⚠ [3/4] Wake-on-LAN requer Administrador para ativar na placa de rede.");
            }

            // 4. Desativar Inicializacao Rapida (Fast Startup)
            if (isAdmin)
            {
                try
                {
                    using (RegistryKey powerKey = Registry.LocalMachine.OpenSubKey(@"SYSTEM\CurrentControlSet\Control\Session Manager\Power", true))
                    {
                        if (powerKey != null)
                        {
                            powerKey.SetValue("HiberbootEnabled", 0, RegistryValueKind.DWord);
                        }
                    }
                    AppendLog("✔ [4/4] Inicialização Rápida ajustada para permitir ligar via Wake-on-LAN.");
                }
                catch (Exception ex)
                {
                    AppendLog("⚠ [4/4] Aviso ao ajustar Inicialização Rápida: " + ex.Message);
                }
            }

            AppendLog("================================================================");
            AppendLog("PRONTO! Abra o app no celular e toque em 'Buscar PC na Rede'.");
        }

        private void EnableWolInRegistry()
        {
            try
            {
                using (RegistryKey netClass = Registry.LocalMachine.OpenSubKey(@"SYSTEM\CurrentControlSet\Control\Class\{4d36e972-e325-11ce-bfc1-08002be10318}", true))
                {
                    if (netClass == null) return;
                    foreach (string subName in netClass.GetSubKeyNames())
                    {
                        if (subName.Length != 4) continue;
                        try
                        {
                            using (RegistryKey subKey = netClass.OpenSubKey(subName, true))
                            {
                                if (subKey == null) continue;
                                string driverDesc = Convert.ToString(subKey.GetValue("DriverDesc", ""));
                                if (!string.IsNullOrEmpty(activeAdapterDescription) &&
                                    driverDesc.Equals(activeAdapterDescription, StringComparison.OrdinalIgnoreCase))
                                {
                                    subKey.SetValue("*WakeOnMagicPacket", "1", RegistryValueKind.String);
                                    subKey.SetValue("*WakeOnPattern", "1", RegistryValueKind.String);
                                    subKey.SetValue("PnPCapabilities", 0, RegistryValueKind.DWord);
                                }
                            }
                        }
                        catch { }
                    }
                }
            }
            catch { }
        }

        private void RunHiddenCommand(string fileName, string arguments)
        {
            ProcessStartInfo psi = new ProcessStartInfo
            {
                FileName = fileName,
                Arguments = arguments,
                CreateNoWindow = true,
                UseShellExecute = false,
                WindowStyle = ProcessWindowStyle.Hidden
            };
            using (Process p = Process.Start(psi))
            {
                if (p != null) p.WaitForExit(8000);
            }
        }

        private string BuildStatusJson()
        {
            DetectNetworkInfo();
            bool wakeArmed = IsWakeArmed();
            bool fastStartupDisabled = IsFastStartupDisabled();
            bool readyForWol = isEthernetAdapter && wakeArmed && fastStartupDisabled;

            string wolDiagJson = string.Format(
                "{{\"isEthernet\":{0},\"adapterName\":\"{1}\",\"wakeArmed\":{2},\"fastStartupDisabled\":{3},\"readyForWol\":{4}}}",
                isEthernetAdapter ? "true" : "false",
                EscapeJson(activeAdapterDescription),
                wakeArmed ? "true" : "false",
                fastStartupDisabled ? "true" : "false",
                readyForWol ? "true" : "false"
            );

            return string.Format(
                "{{\"status\":\"online\",\"hostname\":\"{0}\",\"ip\":\"{1}\",\"mac\":\"{2}\",\"port\":{3},\"requiresPin\":{4},\"wolDiagnostics\":{5}}}",
                EscapeJson(currentHost),
                EscapeJson(currentIp),
                EscapeJson(currentMac),
                HTTP_PORT,
                string.IsNullOrEmpty(currentPin) ? "false" : "true",
                wolDiagJson
            );
        }

        private void StartUdpDiscoveryServer()
        {
            try
            {
                udpDiscoveryListener = new UdpClient(DISCOVERY_UDP_PORT);
                udpDiscoveryListener.EnableBroadcast = true;
                udpThread = new Thread(() =>
                {
                    while (isRunning)
                    {
                        try
                        {
                            IPEndPoint remoteEp = new IPEndPoint(IPAddress.Any, 0);
                            byte[] data = udpDiscoveryListener.Receive(ref remoteEp);
                            string msg = Encoding.UTF8.GetString(data).Trim();
                            if (msg.StartsWith("DISCOVER_PCPOWER", StringComparison.OrdinalIgnoreCase))
                            {
                                byte[] reply = Encoding.UTF8.GetBytes(BuildStatusJson());
                                udpDiscoveryListener.Send(reply, reply.Length, remoteEp);
                                AppendLog("🔍 Descoberta automática respondida para " + remoteEp.Address);
                            }
                        }
                        catch
                        {
                            if (!isRunning) break;
                        }
                    }
                })
                {
                    IsBackground = true
                };
                udpThread.Start();
                AppendLog(string.Format("✔ Descoberta Automática UDP ativa na porta {0}", DISCOVERY_UDP_PORT));
            }
            catch (Exception ex)
            {
                AppendLog("⚠ Porta UDP 5051 ocupada: " + ex.Message);
            }
        }

        private void StartHttpServer()
        {
            if (isRunning) return;
            try
            {
                tcpListener = new TcpListener(IPAddress.Any, HTTP_PORT);
                tcpListener.Start();
                isRunning = true;

                serverThread = new Thread(ServerLoop)
                {
                    IsBackground = true
                };
                serverThread.Start();
                AppendLog(string.Format("✔ Servidor HTTP escutando em 0.0.0.0:{0}", HTTP_PORT));
            }
            catch (Exception ex)
            {
                AppendLog("⚠ Porta 5050 já está em uso por outra instância (" + ex.Message + ").");
            }
        }

        private void ServerLoop()
        {
            while (isRunning)
            {
                try
                {
                    TcpClient client = tcpListener.AcceptTcpClient();
                    ThreadPool.QueueUserWorkItem(_ => HandleClient(client));
                }
                catch
                {
                    if (!isRunning) break;
                }
            }
        }

        private bool IsIpBlocked(string clientIp)
        {
            lock (securityLock)
            {
                if (blockedIps.ContainsKey(clientIp))
                {
                    if (DateTime.UtcNow < blockedIps[clientIp])
                    {
                        return true;
                    }
                    blockedIps.Remove(clientIp);
                    failedAttempts.Remove(clientIp);
                }
                return false;
            }
        }

        private void RegisterFailedAttempt(string clientIp)
        {
            lock (securityLock)
            {
                int count = 1;
                if (failedAttempts.ContainsKey(clientIp))
                {
                    count = failedAttempts[clientIp] + 1;
                }
                failedAttempts[clientIp] = count;

                if (count >= 5)
                {
                    blockedIps[clientIp] = DateTime.UtcNow.AddMinutes(15);
                    AppendLog("🚨 ALERTA: IP " + clientIp + " bloqueado por 15 minutos (5 tentativas inválidas de PIN).");
                }
            }
        }

        private void ResetFailedAttempts(string clientIp)
        {
            lock (securityLock)
            {
                if (failedAttempts.ContainsKey(clientIp))
                {
                    failedAttempts.Remove(clientIp);
                }
            }
        }

        private bool IsPinAuthorized(string rawRequest)
        {
            if (string.IsNullOrEmpty(currentPin)) return true;

            Match headerMatch = Regex.Match(rawRequest, @"X-Auth-Pin:\s*([^\r\n]+)", RegexOptions.IgnoreCase);
            if (headerMatch.Success && headerMatch.Groups[1].Value.Trim() == currentPin)
            {
                return true;
            }

            Match jsonMatch = Regex.Match(rawRequest, "\"pin\"\\s*:\\s*\"([^\"]*)\"");
            if (jsonMatch.Success && jsonMatch.Groups[1].Value.Trim() == currentPin)
            {
                return true;
            }

            return false;
        }

        private int ExtractDelayFromJson(string rawRequest, int defaultDelay)
        {
            try
            {
                Match match = Regex.Match(rawRequest, "\"delay\"\\s*:\\s*(\\d+)");
                if (match.Success)
                {
                    return Math.Max(0, Math.Min(3600, int.Parse(match.Groups[1].Value)));
                }
            }
            catch { }
            return defaultDelay;
        }

        private void HandleClient(TcpClient client)
        {
            using (client)
            {
                try
                {
                    string clientIp = "unknown";
                    IPEndPoint ep = client.Client.RemoteEndPoint as IPEndPoint;
                    if (ep != null)
                    {
                        clientIp = ep.Address.ToString();
                    }

                    if (IsIpBlocked(clientIp))
                    {
                        AppendLog("⛔ Conexão rejeitada: IP " + clientIp + " temporariamente bloqueado por força bruta.");
                        return;
                    }

                    client.ReceiveTimeout = 3000;
                    client.SendTimeout = 3000;
                    using (NetworkStream stream = client.GetStream())
                    {
                        byte[] buffer = new byte[4096];
                        int bytesRead = stream.Read(buffer, 0, buffer.Length);
                        if (bytesRead <= 0) return;

                        string rawRequest = Encoding.UTF8.GetString(buffer, 0, bytesRead);
                        string[] lines = rawRequest.Split(new[] { "\r\n" }, StringSplitOptions.None);
                        if (lines.Length == 0) return;

                        string[] requestParts = lines[0].Split(' ');
                        if (requestParts.Length < 2) return;

                        string method = requestParts[0].ToUpperInvariant();
                        string path = requestParts[1].Split('?')[0];

                        // PROTEÇÃO ANTI-CSRF / BROWSER EXPLOIT:
                        // Rejeita requisições originadas por navegadores da internet (Origin ou Referer de sites externos)
                        bool hasOrigin = Regex.IsMatch(rawRequest, @"\r\nOrigin:\s*http", RegexOptions.IgnoreCase);
                        bool hasReferer = Regex.IsMatch(rawRequest, @"\r\nReferer:\s*http", RegexOptions.IgnoreCase);
                        bool hasClientHeader = Regex.IsMatch(rawRequest, @"\r\nX-PC-Power-Client:\s*1", RegexOptions.IgnoreCase);

                        if (hasOrigin || hasReferer)
                        {
                            AppendLog("🛑 Bloqueio CSRF: Tentativa de acesso originada por navegador web externo descartada de " + clientIp);
                            SendHttpResponse(stream, 403, "{\"ok\":false,\"message\":\"Acesso proibido via navegador web (CSRF Protection).\"}");
                            return;
                        }

                        if (method == "OPTIONS")
                        {
                            SendHttpResponse(stream, 204, "{}");
                            return;
                        }

                        if (method == "GET" && (path == "/status" || path == "/"))
                        {
                            SendHttpResponse(stream, 200, BuildStatusJson());
                            return;
                        }

                        if (method == "POST")
                        {
                            // Para comandos críticos de desligamento/reinício/sleep, exige o cabeçalho do app
                            if (!hasClientHeader)
                            {
                                AppendLog("⛔ Bloqueio de segurança: Header X-PC-Power-Client ausente em POST de " + clientIp);
                                SendHttpResponse(stream, 400, "{\"ok\":false,\"message\":\"Cliente não identificado.\"}");
                                return;
                            }

                            if (!IsPinAuthorized(rawRequest))
                            {
                                RegisterFailedAttempt(clientIp);
                                AppendLog("⛔ Tentativa bloqueada: PIN incorreto ou não informado de " + clientIp);
                                SendHttpResponse(stream, 401, "{\"ok\":false,\"message\":\"PIN de segurança incorreto ou não informado.\"}");
                                return;
                            }

                            ResetFailedAttempts(clientIp);

                            if (path == "/shutdown")
                            {
                                int delay = ExtractDelayFromJson(rawRequest, 5);
                                AppendLog(string.Format("📲 Comando de DESLIGAR recebido pelo celular! Desligando em {0}s...", delay));
                                RunHiddenCommand("shutdown", string.Format("/s /f /t {0} /c \"Desligamento solicitado pelo aplicativo Android (PC Power Remote).\"", delay));
                                SendHttpResponse(stream, 200, string.Format("{{\"ok\":true,\"message\":\"Comando recebido! O computador será desligado em {0} segundos.\"}}", delay));
                            }
                            else if (path == "/restart")
                            {
                                int delay = ExtractDelayFromJson(rawRequest, 5);
                                AppendLog(string.Format("📲 Comando de REINICIAR recebido pelo celular! Reiniciando em {0}s...", delay));
                                RunHiddenCommand("shutdown", string.Format("/r /f /t {0} /c \"Reinício solicitado pelo aplicativo Android (PC Power Remote).\"", delay));
                                SendHttpResponse(stream, 200, string.Format("{{\"ok\":true,\"message\":\"Comando recebido! O computador será reiniciado em {0} segundos.\"}}", delay));
                            }
                            else if (path == "/sleep")
                            {
                                AppendLog("📲 Comando de SUSPENDER (Sleep) recebido pelo celular!");
                                ThreadPool.QueueUserWorkItem(_ =>
                                {
                                    Thread.Sleep(800);
                                    NativeMethods.SetSuspendState(false, true, true);
                                });
                                SendHttpResponse(stream, 200, "{\"ok\":true,\"message\":\"Computador entrando em modo de suspensão...\"}");
                            }
                            else if (path == "/hibernate")
                            {
                                AppendLog("📲 Comando de HIBERNAR recebido pelo celular!");
                                ThreadPool.QueueUserWorkItem(_ =>
                                {
                                    Thread.Sleep(800);
                                    NativeMethods.SetSuspendState(true, true, true);
                                });
                                SendHttpResponse(stream, 200, "{\"ok\":true,\"message\":\"Computador entrando em hibernação...\"}");
                            }
                            else if (path == "/lock")
                            {
                                AppendLog("📲 Comando de BLOQUEAR TELA (Win+L) recebido pelo celular!");
                                NativeMethods.LockWorkStation();
                                SendHttpResponse(stream, 200, "{\"ok\":true,\"message\":\"Tela do computador bloqueada com sucesso!\"}");
                            }
                            else if (path == "/cancel-shutdown")
                            {
                                AppendLog("📲 Comando de CANCELAR DESLIGAMENTO recebido pelo celular.");
                                RunHiddenCommand("shutdown", "/a");
                                SendHttpResponse(stream, 200, "{\"ok\":true,\"message\":\"Desligamento/reinício cancelado com sucesso!\"}");
                            }
                            else
                            {
                                SendHttpResponse(stream, 404, "{\"ok\":false,\"message\":\"Endpoint nao encontrado\"}");
                            }
                            return;
                        }

                        SendHttpResponse(stream, 404, "{\"ok\":false,\"message\":\"Endpoint nao encontrado\"}");
                    }
                }
                catch { }
            }
        }

        private void SendHttpResponse(NetworkStream stream, int statusCode, string jsonBody)
        {
            string statusText = statusCode == 200 ? "OK" : (statusCode == 204 ? "No Content" : (statusCode == 401 ? "Unauthorized" : (statusCode == 403 ? "Forbidden" : (statusCode == 400 ? "Bad Request" : "Not Found"))));
            byte[] bodyBytes = Encoding.UTF8.GetBytes(jsonBody);
            // ZERO CORS WILDCARD: Remove Access-Control-Allow-Origin: * para impedir sites web de chamar o agente
            string headers =
                string.Format("HTTP/1.1 {0} {1}\r\n", statusCode, statusText) +
                "Content-Type: application/json; charset=utf-8\r\n" +
                "X-Content-Type-Options: nosniff\r\n" +
                string.Format("Content-Length: {0}\r\n", bodyBytes.Length) +
                "Connection: close\r\n\r\n";

            byte[] headerBytes = Encoding.UTF8.GetBytes(headers);
            stream.Write(headerBytes, 0, headerBytes.Length);
            stream.Write(bodyBytes, 0, bodyBytes.Length);
            stream.Flush();
        }

        private string EscapeJson(string s)
        {
            if (string.IsNullOrEmpty(s)) return "";
            return s.Replace("\\", "\\\\").Replace("\"", "\\\"");
        }
    }
}
