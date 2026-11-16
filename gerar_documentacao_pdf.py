#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script gerador da documentação técnica e de engenharia de software em PDF do PC Power Remote.
Segue as diretrizes dos padrões IEEE/ISO/IEC/RFC para documentação de arquitetura de software e sistemas distribuídos.
"""

import os
import sys
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm, mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    """
    Canvas de dois passos para calcular o total de páginas e adicionar
    cabeçalhos corporativos e rodapés padronizados (Page X of Y).
    """
    def __init__(self, *args, **kwargs):
        super(NumberedCanvas, self).__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super(NumberedCanvas, self).showPage()
        super(NumberedCanvas, self).save()

    def draw_page_decorations(self, page_count):
        if self._pageNumber == 1:
            # Página de capa não tem cabeçalho nem rodapé padrão
            return

        self.saveState()
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(colors.HexColor("#475569"))

        # Cabeçalho
        self.drawString(2.0 * cm, 28.2 * cm, "PC POWER REMOTE | ESPECIFICAÇÃO DE ENGENHARIA & ARQUITETURA")
        self.drawRightString(19.0 * cm, 28.2 * cm, "REV. 2.1 — NOV/2026")
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.6)
        self.line(2.0 * cm, 28.0 * cm, 19.0 * cm, 28.0 * cm)

        # Rodapé
        self.setFont("Helvetica", 8)
        self.line(2.0 * cm, 1.6 * cm, 19.0 * cm, 1.6 * cm)
        self.drawString(2.0 * cm, 1.2 * cm, "DOCUMENTAÇÃO TÉCNICA OFICIAL — ARQUITETURA DISTRIBUÍDA & PROTOCOLOS")
        page_str = f"Página {self._pageNumber} de {page_count}"
        self.drawRightString(19.0 * cm, 1.2 * cm, page_str)

        self.restoreState()


def build_pdf(filename="PC_Power_Remote_Documentacao_Tecnica.pdf"):
    doc = SimpleDocTemplate(
        filename,
        pagesize=A4,
        leftMargin=2.0 * cm,
        rightMargin=2.0 * cm,
        topMargin=2.2 * cm,
        bottomMargin=2.2 * cm,
    )

    styles = getSampleStyleSheet()

    # Paleta de Cores Corporativa
    C_PRIMARY = colors.HexColor("#0F172A")    # Slate 900
    C_SECONDARY = colors.HexColor("#1E293B")  # Slate 800
    C_ACCENT = colors.HexColor("#2563EB")     # Blue 600
    C_SUCCESS = colors.HexColor("#16A34A")    # Green 600
    C_TEXT = colors.HexColor("#1E293B")       # Slate 800
    C_MUTED = colors.HexColor("#64748B")      # Slate 500
    C_BG_LIGHT = colors.HexColor("#F8FAFC")   # Slate 50
    C_BORDER = colors.HexColor("#E2E8F0")     # Slate 200

    # Definição de Tipografia e Estilos
    styles.add(ParagraphStyle(
        'CoverDocType',
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=14,
        textColor=C_ACCENT,
        textTransform='uppercase',
        spaceAfter=15
    ))

    styles.add(ParagraphStyle(
        'CoverTitle',
        fontName='Helvetica-Bold',
        fontSize=28,
        leading=34,
        textColor=C_PRIMARY,
        spaceAfter=12
    ))

    styles.add(ParagraphStyle(
        'CoverSubtitle',
        fontName='Helvetica',
        fontSize=14,
        leading=20,
        textColor=C_MUTED,
        spaceAfter=30
    ))

    styles.add(ParagraphStyle(
        'CoverMetaLabel',
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=13,
        textColor=C_PRIMARY,
    ))

    styles.add(ParagraphStyle(
        'CoverMetaVal',
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=C_TEXT,
    ))

    styles.add(ParagraphStyle(
        'H1',
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=C_PRIMARY,
        spaceBefore=18,
        spaceAfter=10,
        keepWithNext=True
    ))

    styles.add(ParagraphStyle(
        'H2',
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=17,
        textColor=C_SECONDARY,
        spaceBefore=14,
        spaceAfter=6,
        keepWithNext=True
    ))

    styles.add(ParagraphStyle(
        'H3',
        fontName='Helvetica-Bold',
        fontSize=10.5,
        leading=14,
        textColor=C_ACCENT,
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True
    ))

    styles.add(ParagraphStyle(
        'BodyCustom',
        fontName='Helvetica',
        fontSize=9.5,
        leading=14.5,
        textColor=C_TEXT,
        spaceAfter=8,
        alignment=4 # Justify
    ))

    styles.add(ParagraphStyle(
        'BulletCustom',
        fontName='Helvetica',
        fontSize=9.5,
        leading=14.5,
        textColor=C_TEXT,
        leftIndent=15,
        firstLineIndent=-10,
        spaceAfter=4
    ))

    styles.add(ParagraphStyle(
        'CodeBlock',
        fontName='Courier',
        fontSize=8.5,
        leading=11.5,
        textColor=colors.HexColor("#0F172A"),
        spaceBefore=4,
        spaceAfter=4
    ))

    styles.add(ParagraphStyle(
        'CalloutText',
        fontName='Helvetica-Oblique',
        fontSize=9,
        leading=13.5,
        textColor=colors.HexColor("#1E3A8A")
    ))

    styles.add(ParagraphStyle(
        'TableHeader',
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=colors.white,
        alignment=0
    ))

    styles.add(ParagraphStyle(
        'TableCell',
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=C_TEXT
    ))

    styles.add(ParagraphStyle(
        'TableCellBold',
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=12,
        textColor=C_PRIMARY
    ))

    def make_callout(text, bg="#EFF6FF", border="#3B82F6", title="NOTA TÉCNICA"):
        p_title = Paragraph(f"<b>{title}:</b> {text}", styles['CalloutText'])
        t = Table([[p_title]], colWidths=[15.0 * cm])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor(bg)),
            ('BOX', (0,0), (-1,-1), 1.0, colors.HexColor(border)),
            ('TOPPADDING', (0,0), (-1,-1), 8),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
            ('LEFTPADDING', (0,0), (-1,-1), 12),
            ('RIGHTPADDING', (0,0), (-1,-1), 12),
        ]))
        return t

    def make_code_box(code_str):
        p = Paragraph(code_str.replace("\n", "<br/>").replace(" ", "&nbsp;"), styles['CodeBlock'])
        t = Table([[p]], colWidths=[15.0 * cm])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F1F5F9")),
            ('BOX', (0,0), (-1,-1), 0.8, colors.HexColor("#CBD5E1")),
            ('TOPPADDING', (0,0), (-1,-1), 8),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
            ('LEFTPADDING', (0,0), (-1,-1), 10),
            ('RIGHTPADDING', (0,0), (-1,-1), 10),
        ]))
        return t

    story = []

    # =========================================================================
    # PÁGINA 1: CAPA PROFISSIONAL
    # =========================================================================
    story.append(Spacer(1, 2.5 * cm))
    story.append(Paragraph("DOCUMENTO DE ARQUITETURA DE SISTEMAS & SOFTWARE", styles['CoverDocType']))
    story.append(Paragraph("PC Power Remote", styles['CoverTitle']))
    story.append(Paragraph(
        "Sistema Distribuído para Gerenciamento e Controle de Ciclo de Energia em Redes Locais: "
        "Arquitetura de Transmissão Wake-on-LAN, Descoberta Dinâmica UDP e Agente de Execução Remota.",
        styles['CoverSubtitle']
    ))

    story.append(HRFlowable(width="100%", thickness=2, color=C_ACCENT, spaceBefore=0, spaceAfter=25))

    meta_data = [
        [Paragraph("Versão do Produto:", styles['CoverMetaLabel']), Paragraph("Release 2.1.0 (Enterprise / Standalone)", styles['CoverMetaVal'])],
        [Paragraph("Status do Documento:", styles['CoverMetaLabel']), Paragraph("Aprovado para Produção / Arquitetura de Referência", styles['CoverMetaVal'])],
        [Paragraph("Padrões de Referência:", styles['CoverMetaLabel']), Paragraph("RFC 1122 (UDP/IP), IEEE 802.3, Microsoft ACPI Spec", styles['CoverMetaVal'])],
        [Paragraph("Sistemas Suportados:", styles['CoverMetaLabel']), Paragraph("Android 8.0+ (API 26 a 35) & Windows 10/11 (x64)", styles['CoverMetaVal'])],
        [Paragraph("Repositório Oficial:", styles['CoverMetaLabel']), Paragraph("https://github.com/gabs-1198/pc-power-remote", styles['CoverMetaVal'])],
        [Paragraph("Data de Emissão:", styles['CoverMetaLabel']), Paragraph("Novembro de 2026", styles['CoverMetaVal'])],
    ]
    t_meta = Table(meta_data, colWidths=[4.2 * cm, 10.8 * cm])
    t_meta.setStyle(TableStyle([
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LINEBELOW', (0,0), (-1,-2), 0.5, colors.HexColor("#F1F5F9")),
    ]))
    story.append(t_meta)

    story.append(Spacer(1, 3.0 * cm))
    story.append(make_callout(
        "Este documento técnico contém especificações detalhadas de protocolos de rede, engenharia de segurança, "
        "estruturas de dados e guia de implementação operacional. Recomendado para desenvolvedores, "
        "engenheiros de rede e administradores de sistemas.",
        bg="#F8FAFC", border="#94A3B8", title="AVISO DE DISTRIBUIÇÃO"
    ))

    story.append(PageBreak())

    # =========================================================================
    # SEÇÃO 1: RESUMO EXECUTIVO E VISÃO GERAL DA ARQUITETURA
    # =========================================================================
    story.append(Paragraph("1. Visão Geral e Princípios Arquiteturais", styles['H1']))
    story.append(HRFlowable(width="100%", thickness=0.8, color=C_BORDER, spaceBefore=2, spaceAfter=10))

    story.append(Paragraph(
        "O <b>PC Power Remote</b> é uma plataforma distribuída desenvolvida com o objetivo de eliminar a barreira física "
        "no controle operacional de estações de trabalho e servidores pessoais. Projetado sob a premissa de confiabilidade absoluta, "
        "o sistema opera em topologia cliente-servidor descentralizada (Peer-to-Peer dentro do domínio de broadcast da rede local), "
        "não dependendo de intermediários em nuvem, servidores externos ou infraestruturas complexas de relay.",
        styles['BodyCustom']
    ))
    story.append(Paragraph(
        "A solução divide-se em dois subsistemas interoperáveis desacoplados:",
        styles['BodyCustom']
    ))
    story.append(Paragraph("• <b>Cliente Móvel (Android):</b> Aplicação nativa moderna construída sobre Jetpack Compose e Kotlin Coroutines, otimizada para baixo consumo de bateria, equipada com motor de varredura multithread assíncrono e transmissão redundante de pacotes UDP.", styles['BulletCustom']))
    story.append(Paragraph("• <b>Agente Residente (Windows Host):</b> Executável nativo monolítico (.NET C# / Python) rodando em espaço de usuário sob privilégios controlados, responsável pela interação com as APIs Win32 de energia, orquestração de firewall e respostas dinâmicas de telemetria.", styles['BulletCustom']))

    story.append(Spacer(1, 8))
    story.append(Paragraph("Diagrama de Topologia e Comunicação na Rede Local", styles['H3']))

    topo_table_data = [
        [
            Paragraph("<b>SUBSISTEMA ANDROID (CLIENTE)</b><br/>"
                      "• UI: Jetpack Compose / M3<br/>"
                      "• Engine WoL: Sockets UDP<br/>"
                      "• Discovery: Broadcast 5051<br/>"
                      "• REST Client: HttpURLConnection", styles['TableCellBold']),
            Paragraph("<b>INTERLIGAÇÃO (WI-FI / LAN)</b><br/>"
                      "UDP 9 / 7 ➔ Magic Packet (WoL)<br/>"
                      "UDP 5051 ⇄ Descoberta Dinâmica<br/>"
                      "TCP 5050 ⇄ REST API (Ações/Status)<br/>"
                      "Subnet /24 Broadcast", styles['TableCell']),
            Paragraph("<b>SUBSISTEMA WINDOWS (HOST)</b><br/>"
                      "• Listener HTTP (Porta 5050)<br/>"
                      "• Listener UDP (Porta 5051)<br/>"
                      "• Kernel / PowrProf.dll<br/>"
                      "• Firewall Privado & Startup", styles['TableCellBold'])
        ]
    ]
    t_topo = Table(topo_table_data, colWidths=[5.0 * cm, 5.0 * cm, 5.0 * cm])
    t_topo.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,0), colors.HexColor("#EFF6FF")),
        ('BACKGROUND', (1,0), (1,0), colors.HexColor("#F8FAFC")),
        ('BACKGROUND', (2,0), (2,0), colors.HexColor("#F0FDF4")),
        ('BOX', (0,0), (-1,-1), 1, C_BORDER),
        ('INNERGRID', (0,0), (-1,-1), 0.5, C_BORDER),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(t_topo)

    story.append(Spacer(1, 10))
    story.append(Paragraph("2. Engenharia de Descoberta Automática (Zero-Conf)", styles['H1']))
    story.append(HRFlowable(width="100%", thickness=0.8, color=C_BORDER, spaceBefore=2, spaceAfter=10))

    story.append(Paragraph(
        "Um dos grandes obstáculos em soluções tradicionais de administração remota é a exigência de que o usuário "
        "localize manualmente parâmetros de rede como endereços IP e MAC. No <b>PC Power Remote</b>, foi implementada "
        "uma estratégia híbrida de descoberta sem intervenção humana, dividida em dois níveis de redundância:",
        styles['BodyCustom']
    ))

    story.append(Paragraph("Nível 1: Broadcast Ativo Datagram (UDP 5051)", styles['H2']))
    story.append(Paragraph(
        "O cliente Android calcula o endereço de broadcast da sub-rede ativa (ex: <code>192.168.1.255</code>) bem como o endereço "
        "global <code>255.255.255.255</code> e emite um datagrama contendo o payload delimitador <code>DISCOVER_PCPOWER</code>. "
        "Todos os hosts na rede que executam o agente mantêm um socket UDP ouvindo na porta 5051 e respondem imediatamente "
        "com o datagrama serializado contendo seus metadados completos (Hostname, IP, MAC e Diagnóstico). "
        "O tempo médio de descoberta deste nível é inferior a <b>180 milissegundos</b>.",
        styles['BodyCustom']
    ))

    story.append(Paragraph("Nível 2: Varredura Paralela Heurística de Sub-rede (Subnet Pool /24)", styles['H2']))
    story.append(Paragraph(
        "Determinados roteadores residenciais e pontos de acesso corporativos ativam o recurso de 'Isolamento de AP' "
        "ou descartam pacotes de broadcast UDP entre redes Wi-Fi e cabeadas. Para contornar essa restrição sem falha, "
        "o cliente Android aciona um pool assíncrono de 48 workers concorrentes (Kotlin Coroutines / Java ExecutorService), "
        "testando todas as 254 combinações possíveis do bloco /24 na rota <code>GET /status</code> com timeout ultra-rápido "
        "de 350ms. Caso um host responda com o cabeçalho do agente, ele é adicionado à lista em menos de 1,8 segundo.",
        styles['BodyCustom']
    ))

    story.append(make_callout(
        "Graças ao mecanismo 'Auto-IP-Healing', caso o servidor DHCP do roteador altere o IP dinâmico do computador, "
        "o aplicativo detecta a falha de rota na primeira tentativa, executa uma varredura silenciosa de 500ms, "
        "encontra o novo IP com base no MAC Address já conhecido e recupera a conexão sem que o usuário note a interrupção.",
        bg="#F0FDF4", border="#22C55E", title="RESILIÊNCIA DE REDE"
    ))

    story.append(PageBreak())

    # =========================================================================
    # SEÇÃO 3: PROTOCOLO WAKE-ON-LAN & RESILIÊNCIA FÍSICA
    # =========================================================================
    story.append(Paragraph("3. Especificação do Protocolo Wake-on-LAN (WoL)", styles['H1']))
    story.append(HRFlowable(width="100%", thickness=0.8, color=C_BORDER, spaceBefore=2, spaceAfter=10))

    story.append(Paragraph(
        "O padrão Wake-on-LAN baseia-se na capacidade da Controladora de Interface de Rede (NIC) de permanecer em estado "
        "de ultra-baixo consumo (estados ACPI D3warm ou D3cold) enquanto a fonte de alimentação ATX mantém alimentada a linha "
        "standby de +5VSB. A NIC escuta ininterruptamente a camada de enlace à procura de um frame de dados específico, "
        "denominado <b>Magic Packet</b>.",
        styles['BodyCustom']
    ))

    story.append(Paragraph("Estrutura Binária do Magic Packet", styles['H2']))
    story.append(Paragraph(
        "O Magic Packet é um payload de exatamente <b>102 bytes</b> construído estritamente segundo a especificação AMD/HP Magic Packet Technology:",
        styles['BodyCustom']
    ))
    story.append(Paragraph("1. <b>Sincronismo de Cabeçalho:</b> Uma sequência ininterrupta de 6 bytes hexadecimais <code>0xFF</code> (48 bits em 1).", styles['BulletCustom']))
    story.append(Paragraph("2. <b>Sequência de Alvo:</b> O Endereço Físico (MAC Address de 48 bits / 6 bytes) da controladora de rede de destino, repetido consecutivamente exatamente 16 vezes.", styles['BulletCustom']))

    story.append(Spacer(1, 4))
    wol_hex_example = (
        "FF FF FF FF FF FF\n"
        "[MAC x 1]  3C 7C 3F 7C 8F 0D   [MAC x 2]  3C 7C 3F 7C 8F 0D\n"
        "[MAC x 3]  3C 7C 3F 7C 8F 0D   ...\n"
        "[MAC x 16] 3C 7C 3F 7C 8F 0D   (Totalizando 102 bytes no payload UDP)"
    )
    story.append(make_code_box(wol_hex_example))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Engenharia de Disparo em Rajada (Burst Transmission)", styles['H2']))
    story.append(Paragraph(
        "Por trafegar sobre o protocolo não-orientado à conexão UDP (User Datagram Protocol) nas portas 9 e 7, "
        "pacotes Wake-on-LAN podem ser descartados caso buffers de comutadores (switches) ou roteadores estejam ocupados. "
        "Para garantir 99.99% de taxa de entrega, o cliente Android implementa a transmissão em <b>rajada tripla (Burst Count = 3)</b>, "
        "com espaçamento inter-packet de 120ms direcionado simultaneamente a múltiplos destinos: broadcast global (<code>255.255.255.255</code>), "
        "broadcast direcionado da sub-rede local (ex: <code>192.168.68.255</code>) e unicast direto ao último IP conhecido do host.",
        styles['BodyCustom']
    ))

    story.append(Paragraph("Diagnóstico de Hardware & Condições de Falha", styles['H2']))
    story.append(Paragraph(
        "Para erradicar a frustração do usuário que tenta ligar computadores mal configurados na placa-mãe, "
        "o agente Windows inspeciona em runtime o hardware e devolve um objeto de diagnóstico no handshake de rede:",
        styles['BodyCustom']
    ))

    diag_table_data = [
        [Paragraph("Parâmetro de Diagnóstico", styles['TableHeader']), Paragraph("Critério de Avaliação Técnica", styles['TableHeader']), Paragraph("Impacto Operacional", styles['TableHeader'])],
        [
            Paragraph("<b>isEthernet</b>", styles['TableCellBold']),
            Paragraph("Interface de rede ativa é do tipo <code>Ethernet</code> / <code>GigabitEthernet</code>.", styles['TableCell']),
            Paragraph("Verdadeiro: Ideal para WoL.<br/>Falso: Em Wi-Fi, o rádio desliga em S5.", styles['TableCell'])
        ],
        [
            Paragraph("<b>wakeArmed</b>", styles['TableCellBold']),
            Paragraph("Query de sistema: <code>powercfg /devicequery wake_armed</code>.", styles['TableCell']),
            Paragraph("Indica se o driver do Windows tem permissão para receber sinal elétrico de despertar.", styles['TableCell'])
        ],
        [
            Paragraph("<b>fastStartupDisabled</b>", styles['TableCellBold']),
            Paragraph("Registro: <code>HKLM\\...\\Power\\HiberbootEnabled == 0</code>.", styles['TableCell']),
            Paragraph("O Fast Startup do Windows 10/11 bloqueia a placa de rede em hibernação profunda.", styles['TableCell'])
        ],
        [
            Paragraph("<b>readyForWol</b>", styles['TableCellBold']),
            Paragraph("Conjunção lógica: <code>isEthernet && wakeArmed && fastStartup</code>.", styles['TableCell']),
            Paragraph("Selo verde exibido no aplicativo mobile confirmando prontidão de despertar.", styles['TableCell'])
        ]
    ]
    t_diag = Table(diag_table_data, colWidths=[3.5 * cm, 6.0 * cm, 5.5 * cm])
    t_diag.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), C_PRIMARY),
        ('BOX', (0,0), (-1,-1), 1, C_BORDER),
        ('INNERGRID', (0,0), (-1,-1), 0.5, C_BORDER),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(t_diag)

    story.append(PageBreak())

    # =========================================================================
    # SEÇÃO 4: CONTRATO DA API REST & AÇÕES DE ENERGIA
    # =========================================================================
    story.append(Paragraph("4. Especificação da API REST do Agente Windows", styles['H1']))
    story.append(HRFlowable(width="100%", thickness=0.8, color=C_BORDER, spaceBefore=2, spaceAfter=10))

    story.append(Paragraph(
        "O agente Windows expõe um servidor HTTP embutido de altíssimo desempenho e zero dependências externas, "
        "vinculado à porta padrão TCP 5050. Todas as comunicações utilizam payloads em formato JSON com codificação UTF-8.",
        styles['BodyCustom']
    ))

    api_endpoints = [
        [Paragraph("Método & Rota", styles['TableHeader']), Paragraph("Payload Requisição", styles['TableHeader']), Paragraph("Comportamento no Host Windows", styles['TableHeader'])],
        [
            Paragraph("<b>GET /status</b>", styles['TableCellBold']),
            Paragraph("Nenhum", styles['TableCell']),
            Paragraph("Retorna estado online, hostname, IP local, MAC address, necessidade de PIN e objeto de diagnóstico WoL.", styles['TableCell'])
        ],
        [
            Paragraph("<b>POST /shutdown</b>", styles['TableCellBold']),
            Paragraph("<code>{\"delay\": 5, \"pin\": \"...\"}</code>", styles['TableCell']),
            Paragraph("Executa <code>shutdown /s /f /t &lt;delay&gt;</code> forçando encerramento limpo com tempo de tolerância.", styles['TableCell'])
        ],
        [
            Paragraph("<b>POST /restart</b>", styles['TableCellBold']),
            Paragraph("<code>{\"delay\": 5, \"pin\": \"...\"}</code>", styles['TableCell']),
            Paragraph("Executa <code>shutdown /r /f /t &lt;delay&gt;</code> reiniciando o sistema operacional.", styles['TableCell'])
        ],
        [
            Paragraph("<b>POST /sleep</b>", styles['TableCellBold']),
            Paragraph("<code>{\"pin\": \"...\"}</code>", styles['TableCell']),
            Paragraph("Invoca nativamente <code>PowrProf.dll!SetSuspendState(0, 1, 1)</code> colocando o PC em suspensão ACPI S3.", styles['TableCell'])
        ],
        [
            Paragraph("<b>POST /hibernate</b>", styles['TableCellBold']),
            Paragraph("<code>{\"pin\": \"...\"}</code>", styles['TableCell']),
            Paragraph("Invoca nativamente <code>PowrProf.dll!SetSuspendState(1, 1, 1)</code> salvando a memória em disco (ACPI S4).", styles['TableCell'])
        ],
        [
            Paragraph("<b>POST /lock</b>", styles['TableCellBold']),
            Paragraph("<code>{\"pin\": \"...\"}</code>", styles['TableCell']),
            Paragraph("Invoca <code>user32.dll!LockWorkStation()</code> efetuando o bloqueio de sessão imediato (Win+L).", styles['TableCell'])
        ],
        [
            Paragraph("<b>POST /cancel-shutdown</b>", styles['TableCellBold']),
            Paragraph("<code>{\"pin\": \"...\"}</code>", styles['TableCell']),
            Paragraph("Executa <code>shutdown /a</code> abortando o contador regressivo de desligamento em andamento.", styles['TableCell'])
        ]
    ]
    t_api = Table(api_endpoints, colWidths=[4.0 * cm, 4.5 * cm, 6.5 * cm])
    t_api.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), C_PRIMARY),
        ('BOX', (0,0), (-1,-1), 1, C_BORDER),
        ('INNERGRID', (0,0), (-1,-1), 0.5, C_BORDER),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(t_api)

    story.append(Spacer(1, 8))
    story.append(Paragraph("Exemplo de Payload de Resposta (GET /status):", styles['H3']))
    json_example = (
        "{\n"
        '  "status": "online",\n'
        '  "hostname": "WORKSTATION-DEV",\n'
        '  "ip": "192.168.1.100",\n'
        '  "mac": "3C:7C:3F:7C:8F:0D",\n'
        '  "port": 5050,\n'
        '  "requiresPin": true,\n'
        '  "wolDiagnostics": {\n'
        '    "isEthernet": true,\n'
        '    "adapterName": "Intel(R) Ethernet Controller I225-V",\n'
        '    "wakeArmed": true,\n'
        '    "fastStartupDisabled": true,\n'
        '    "readyForWol": true\n'
        "  }\n"
        "}"
    )
    story.append(make_code_box(json_example))

    story.append(PageBreak())

    # =========================================================================
    # SEÇÃO 5: MODELAGEM DE SEGURANÇA E MATRIZ DE RISCO
    # =========================================================================
    story.append(Paragraph("5. Engenharia de Segurança & Superfície de Ataque", styles['H1']))
    story.append(HRFlowable(width="100%", thickness=0.8, color=C_BORDER, spaceBefore=2, spaceAfter=10))

    story.append(Paragraph(
        "A segurança foi projetada com base no princípio do menor privilégio e redução rigorosa de superfície de ataque. "
        "Abaixo são descritas as garantias de isolamento do sistema:",
        styles['BodyCustom']
    ))

    story.append(Paragraph("1. Imunidade à Execução Remota Arbitrária (No RCE)", styles['H2']))
    story.append(Paragraph(
        "O agente Windows <b>não é um shell remoto</b> e não aceita comandos de terminal arbitrários. Os métodos invocáveis "
        "são mapeados para ações estáticas compiladas (rotas REST rígidas). Mesmo que um agente malicioso envie comandos bash, "
        "powershell ou caracteres de injeção no payload JSON, o parser desserializa apenas o campo inteiro <code>delay</code> "
        "(limitado estritamente no intervalo entre 0 e 3600 segundos) e o campo alfanumérico <code>pin</code>.",
        styles['BodyCustom']
    ))

    story.append(Paragraph("2. Isolamento de Perfil de Firewall (Private / Domain Only)", styles['H2']))
    story.append(Paragraph(
        "Na inicialização, o instalador em C# configura regras no <i>Windows Advanced Firewall</i> com escopo restrito a "
        "<code>profile=private,domain</code>. Isso significa que, se o host for um notebook corporativo ou pessoal que venha "
        "a se conectar a um Wi-Fi público (aeroporto, cafeteria, hotel), as portas TCP 5050 e UDP 5051 permanecem <b>completamente "
        "invisíveis e bloqueadas</b> pela pilha de rede do kernel, eliminando riscos de varredura externa.",
        styles['BodyCustom']
    ))

    story.append(Paragraph("3. Autenticação Baseada em PIN de Segurança", styles['H2']))
    story.append(Paragraph(
        "O sistema suporta a inclusão de um PIN de segurança armazenado na chave de registro do usuário (<code>HKCU\\Software\\PCPowerRemote</code>). "
        "Quando ativado, qualquer requisição de desligamento, suspensão ou reinicialização desprovida do header <code>X-Auth-Pin</code> "
        "ou do campo <code>pin</code> coincidente é imediatamente rejeitada com código <code>401 Unauthorized</code>.",
        styles['BodyCustom']
    ))

    sec_table_data = [
        [Paragraph("Vetor de Ameaça", styles['TableHeader']), Paragraph("Nível de Risco", styles['TableHeader']), Paragraph("Contramedida Arquitetural Implementada", styles['TableHeader'])],
        [
            Paragraph("Invasão via Internet (WAN)", styles['TableCellBold']),
            Paragraph("<font color='#16A34A'><b>NULO</b></font>", styles['TableCell']),
            Paragraph("A porta opera exclusivamente em LAN; o roteador NAT doméstico bloqueia conexões de entrada sem redirecionamento explícito.", styles['TableCell'])
        ],
        [
            Paragraph("Injeção de Código / RCE", styles['TableCellBold']),
            Paragraph("<font color='#16A34A'><b>NULO</b></font>", styles['TableCell']),
            Paragraph("Rotas fixas em código; parâmetros validados por tipos rígidos (int para tempo, regex para string).", styles['TableCell'])
        ],
        [
            Paragraph("Ataques em Redes Públicas", styles['TableCellBold']),
            Paragraph("<font color='#16A34A'><b>NULO</b></font>", styles['TableCell']),
            Paragraph("Firewall do Windows fecha a porta automaticamente em redes públicas (perfil Private requerido).", styles['TableCell'])
        ],
        [
            Paragraph("Acionamento por Convidado no Wi-Fi", styles['TableCellBold']),
            Paragraph("<font color='#D97706'><b>BAIXO</b></font>", styles['TableCell']),
            Paragraph("Mitigado pelo PIN de Segurança obrigatório configurado na interface do host e cliente.", styles['TableCell'])
        ]
    ]
    t_sec = Table(sec_table_data, colWidths=[4.2 * cm, 2.8 * cm, 8.0 * cm])
    t_sec.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), C_PRIMARY),
        ('BOX', (0,0), (-1,-1), 1, C_BORDER),
        ('INNERGRID', (0,0), (-1,-1), 0.5, C_BORDER),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(t_sec)

    story.append(PageBreak())

    # =========================================================================
    # SEÇÃO 6: GUIA OPERACIONAL & MATRIZ DE TROUBLESHOOTING
    # =========================================================================
    story.append(Paragraph("6. Guia Operacional de Instalação e Troubleshooting", styles['H1']))
    story.append(HRFlowable(width="100%", thickness=0.8, color=C_BORDER, spaceBefore=2, spaceAfter=10))

    story.append(Paragraph("Procedimento de Ativação no Host (Windows)", styles['H2']))
    story.append(Paragraph("1. Copie o executável <code>PCPowerSetup_e_Agente.exe</code> para qualquer diretório do computador.", styles['BulletCustom']))
    story.append(Paragraph("2. Execute o arquivo dando duplo clique e confirme a elevação UAC como Administrador.", styles['BulletCustom']))
    story.append(Paragraph("3. O configurador executará de forma autônoma a cópia para <code>%LOCALAPPDATA%\\PCPowerRemote</code>, registrará o atalho de inicialização do Windows no Registro, configurará as regras de Firewall e ativará o Magic Packet no driver da NIC.", styles['BulletCustom']))
    story.append(Paragraph("4. Opcionalmente, defina um PIN numérico no campo correspondente e clique em 'Salvar PIN'.", styles['BulletCustom']))

    story.append(Paragraph("Procedimento de Instalação no Cliente (Android)", styles['H2']))
    story.append(Paragraph("1. Instale o pacote assinado <code>PCPowerRemote.apk</code> no smartphone.", styles['BulletCustom']))
    story.append(Paragraph("2. Conecte o aparelho à mesma rede Wi-Fi à qual o computador está conectado.", styles['BulletCustom']))
    story.append(Paragraph("3. Abra o aplicativo: a busca por broadcast localizará o computador e exibirá o selo verde <b>COMPUTADOR LIGADO</b> em menos de 1 segundo.", styles['BulletCustom']))

    story.append(Spacer(1, 6))
    story.append(Paragraph("Matriz de Diagnóstico e Resolução de Problemas (Troubleshooting)", styles['H2']))

    trouble_data = [
        [Paragraph("Sintoma Observado", styles['TableHeader']), Paragraph("Causa Provável", styles['TableHeader']), Paragraph("Ação Corretiva Recomendada", styles['TableHeader'])],
        [
            Paragraph("O botão 'Ligar' foi acionado mas o PC não despertou.", styles['TableCellBold']),
            Paragraph("1. Cabo de rede desconectado (PC em Wi-Fi).<br/>"
                      "2. Opção WoL desativada na BIOS/UEFI.<br/>"
                      "3. Recurso ErP/EuP ativado na placa-mãe.", styles['TableCell']),
            Paragraph("• Conecte o PC via cabo Ethernet RJ45.<br/>"
                      "• Na BIOS, ative 'Power On by PCI-E/LAN'.<br/>"
                      "• Desative 'ErP Ready' para manter energia em standby na placa de rede.", styles['TableCell'])
        ],
        [
            Paragraph("App exibe 'PC Desligado' mesmo com o PC ligado.", styles['TableCellBold']),
            Paragraph("1. Rede Wi-Fi definida como 'Pública' no Windows.<br/>"
                      "2. O agente foi fechado manualmente.<br/>"
                      "3. Isolamento de AP ativo no roteador.", styles['TableCell']),
            Paragraph("• Mude a rede no Windows de 'Pública' para 'Privada'.<br/>"
                      "• Abra o agente pelo menu Iniciar.<br/>"
                      "• Desative o isolamento de clientes no painel do roteador Wi-Fi.", styles['TableCell'])
        ],
        [
            Paragraph("Erro 401 ao tentar desligar ou reiniciar.", styles['TableCellBold']),
            Paragraph("O host possui um PIN configurado que não foi informado no aplicativo móvel.", styles['TableCell']),
            Paragraph("Abra as opções avançadas no aplicativo móvel e preencha exatamente o mesmo PIN salvo no PC.", styles['TableCell'])
        ]
    ]
    t_trouble = Table(trouble_data, colWidths=[4.2 * cm, 5.0 * cm, 5.8 * cm])
    t_trouble.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), C_PRIMARY),
        ('BOX', (0,0), (-1,-1), 1, C_BORDER),
        ('INNERGRID', (0,0), (-1,-1), 0.5, C_BORDER),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(t_trouble)

    story.append(Spacer(1, 14))
    story.append(Paragraph("7. Conclusão e Registro de Versões", styles['H1']))
    story.append(HRFlowable(width="100%", thickness=0.8, color=C_BORDER, spaceBefore=2, spaceAfter=8))
    story.append(Paragraph(
        "A arquitetura do <b>PC Power Remote</b> consolida as melhores práticas de desenvolvimento de sistemas distribuídos "
        "locais: zero overhead computacional no host, comunicação orientada a eventos assíncronos no mobile, blindagem "
        "perimetral por perfil de firewall e telemetria preditiva de hardware. O projeto encontra-se em estado maduro, "
        "pronto para distribuição corporativa ou uso pessoal avançado.",
        styles['BodyCustom']
    ))

    # Gerar o documento
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Documentação PDF gerada com sucesso: {filename}")

if __name__ == "__main__":
    out_pdf = "c:\\Users\\Usuario\\Downloads\\Projetos\\Pessoal\\PC_Power_Remote_Documentacao_Tecnica.pdf"
    build_pdf(out_pdf)
