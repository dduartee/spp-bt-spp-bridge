# 🚀 Guia Completo Termux:API — Samsung Galaxy S23
> 📎 Veja também: [README.md](README.md) — projeto BT SPP Bridge

> Documentação detalhada de todas as APIs testadas e funcionando.
> Data: 03/06/2026 | Dispositivo: Samsung Galaxy S23 (Android) | Operadora: VIVO

---

## 📦 Instalação

```bash
# 1. Instalar APK pelo F-Droid
# https://f-droid.org/en/packages/com.termux.api/

# 2. Instalar pacote no Termux
pkg install termux-api
```

---

## 🔋 Bateria

```bash
termux-battery-status
```

**Saída JSON:**

| Campo | Descrição |
|---|---|
| `health` | GOOD / OVERHEAT / DEAD / OVER_VOLTAGE / FAILURE / COLD |
| `plugged` | UNPLUGGED / PLUGGED_AC / PLUGGED_USB / PLUGGED_WIRELESS |
| `status` | CHARGING / DISCHARGING / FULL / NOT_CHARGING |
| `percentage` | 0-100 |
| `temperature` | Celsius |
| `voltage` | mV |
| `current` | mA (negativo = descarregando) |
| `technology` | Li-ion, Li-poly, etc. |

**Exemplo real (S23):**
```json
{
  "health": "GOOD",
  "plugged": "UNPLUGGED",
  "status": "DISCHARGING",
  "percentage": 75,
  "temperature": 29.2,
  "voltage": 3991,
  "current": -1039,
  "technology": "Li-ion"
}
```

---

## 💡 Lanterna (Torch)

```bash
termux-torch on       # Liga
termux-torch off      # Desliga
```

**Exemplo de pisca:**
```bash
for i in 1 2 3; do
  termux-torch on && sleep 0.3 && termux-torch off && sleep 0.3
done
```

---

## 📳 Vibração

```bash
termux-vibrate -d 500    # 500ms
termux-vibrate -d 1000   # 1 segundo
termux-vibrate -d 200    # pulsação curta
```

**Padrão de vibração:**
```bash
for i in 1 2 3; do
  termux-vibrate -d 200
  sleep 0.3
done
```

---

## 📋 Clipboard (Área de Transferência)

```bash
# Copiar texto
termux-clipboard-set "Texto para copiar"

# Ler texto do clipboard
termux-clipboard-get
```

**Exemplo com data/hora:**
```bash
termux-clipboard-set "Copiado em $(date)"
```

---

## 📍 GPS / Localização

**Permissão necessária:** `android.permission.ACCESS_FINE_LOCATION`

```bash
termux-location
```

**Saída JSON:**

| Campo | Descrição |
|---|---|
| `latitude` | Latitude em graus |
| `longitude` | Longitude em graus |
| `altitude` | Altitude em metros |
| `accuracy` | Precisão horizontal (metros) |
| `vertical_accuracy` | Precisão vertical (metros) |
| `bearing` | Direção em graus (0-360) |
| `speed` | Velocidade em m/s |
| `provider` | gps / network / passive |

**Exemplo real:**
```json
{
  "latitude": -27.12038463,
  "longitude": -52.61820145,
  "altitude": 698.34,
  "accuracy": 9.8,
  "vertical_accuracy": 6.82,
  "bearing": 205.89,
  "speed": 0.36,
  "provider": "gps"
}
```

---

## 📸 Câmera

**Permissão necessária:** `android.permission.CAMERA`

```bash
# Câmera traseira (0)
termux-camera-photo -c 0 foto.jpg

# Câmera frontal / selfie (1)
termux-camera-photo -c 1 selfie.jpg

# Salvar no armazenamento compartilhado
termux-camera-photo -c 0 ~/storage/shared/foto.jpg

# Qualidade real S23:
# Traseira: 3060×4080 (12.5 MP) — ~2.2 MB
# Frontal: ~4.7 MB
```

---

## 🎤 Microfone (Gravação)

**Permissão necessária:** `android.permission.RECORD_AUDIO`

```bash
# Gravação por tempo limitado (3 segundos)
termux-microphone-record -f audio.m4a -l 3

# Gravação com limite de tamanho
termux-microphone-record -f audio.m4a -l 10

# Salvar no storage
termux-microphone-record -f ~/storage/shared/gravacao.m4a -l 5
```

---

## 🔊 Áudio Info

```bash
termux-audio-info
```

**Exemplo:**
```json
{
  "PROPERTY_OUTPUT_SAMPLE_RATE": "48000",
  "PROPERTY_OUTPUT_FRAMES_PER_BUFFER": "192",
  "AUDIOTRACK_SAMPLE_RATE": 48000,
  "AUDIOTRACK_BUFFER_SIZE_IN_FRAMES": 4810,
  "AUDIOTRACK_SAMPLE_RATE_LOW_LATENCY": 48000,
  "AUDIOTRACK_BUFFER_SIZE_IN_FRAMES_LOW_LATENCY": 192,
  "BLUETOOTH_A2DP_IS_ON": false,
  "WIREDHEADSET_IS_CONNECTED": false
}
```

---

## 🔉 Volume

```bash
termux-volume
```

**Saída:**
```json
[
  { "stream": "call",         "volume": 15, "max_volume": 15 },
  { "stream": "system",       "volume": 0,  "max_volume": 15 },
  { "stream": "ring",         "volume": 0,  "max_volume": 15 },
  { "stream": "music",        "volume": 0,  "max_volume": 15 },
  { "stream": "alarm",        "volume": 1,  "max_volume": 15 },
  { "stream": "notification", "volume": 0,  "max_volume": 15 }
]
```

**Streams disponíveis:** call, system, ring, music, alarm, notification

---

## 🗣️ TTS (Text-to-Speech)

```bash
# Falar texto
termux-tts-speak "Olá, Termux funcionando perfeitamente!"

# Listar engines disponíveis
termux-tts-engines
```

---

## 🧭 Sensores

```bash
# Listar sensores disponíveis
termux-sensor -l

# Ler acelerômetro (1 amostra)
termux-sensor -s "Accelerometer" -n 1

# Ler sensor por tempo (5 segundos)
termux-sensor -s "Light" -n 5 -d 1000
```

**Exemplo acelerômetro (S23 — LSM6DSO):**
```json
{
  "lsm6dso LSM6DSO Accelerometer Non-wakeup": {
    "values": [-0.11, 3.86, 9.16]
  }
}
```
> X, Y, Z em m/s². Z ≈ 9.8 = gravidade (celular plano na mesa).

---

## 🌐 WiFi

### Conexão atual
```bash
termux-wifi-connectioninfo
```

**Exemplo:**
```json
{
  "bssid": "98:2a:0a:07:39:fb",
  "frequency_mhz": 2457,
  "ip": "10.0.0.35",
  "link_speed_mbps": 78,
  "rssi": -62,
  "ssid": "2NET_ALFF",
  "supplicant_state": "COMPLETED"
}
```

### Scan de redes ao redor
```bash
termux-wifi-scaninfo
```

**Exemplo (15 redes detectadas):**
```json
[
  {
    "bssid": "58:f2:fc:3c:7e:0c",
    "frequency_mhz": 5745,
    "rssi": -81,
    "ssid": "SCNet_PAULO",
    "channel_bandwidth_mhz": "80",
    "capabilities": "[WPA2-PSK-CCMP-128][RSN-PSK-CCMP-128][ESS][WPS]"
  }
]
```

### Ligar/Desligar WiFi
```bash
termux-wifi-enable true   # Liga
termux-wifi-enable false  # Desliga
```

---

## 📡 Rede Celular

### Info da torre
```bash
termux-telephony-cellinfo
```

**Exemplo:**
```json
[
  {
    "type": "wcdma",
    "registered": true,
    "asu": 96,
    "dbm": -24,
    "level": 3,
    "cid": 3262336,
    "lac": 40249,
    "mcc": 724,
    "mnc": 6,
    "psc": 154
  }
]
```

### Info do dispositivo
**Permissão necessária:** `android.permission.READ_PHONE_STATE`

```bash
termux-telephony-deviceinfo
```

```json
{
  "data_enabled": "false",
  "data_state": "disconnected",
  "phone_count": 2,
  "phone_type": "gsm",
  "network_operator": "72406",
  "network_operator_name": "VIVO",
  "network_country_iso": "br",
  "network_type": "hspa",
  "sim_operator": "72406",
  "sim_operator_name": "VIVO",
  "sim_state": "ready"
}
```

---

## 📞 Chamadas (Call Log)

**Permissão necessária:** `android.permission.READ_CALL_LOG`

```bash
termux-call-log
```

```json
[
  {
    "name": "Contato",
    "phone_number": "+5549912345678",
    "type": "MISSED",
    "date": "2026-06-03 10:00:00",
    "duration": "00:00",
    "sim_id": "1"
  }
]
```

**Tipos:** INCOMING, OUTGOING, MISSED, REJECTED, BLOCKED

---

## 📩 SMS

**Permissão necessária:** `android.permission.READ_SMS`

```bash
# Listar últimos 5 SMS
termux-sms-list -l 5

# Listar SMS da caixa de entrada
termux-sms-inbox -l 10
```

```json
[
  {
    "threadid": 15,
    "type": "inbox",
    "read": false,
    "address": "Vivo",
    "number": "Vivo",
    "received": "2026-06-02 14:10:05",
    "body": "Texto da mensagem...",
    "_id": 350
  }
]
```

### Enviar SMS
**Permissão necessária:** `android.permission.SEND_SMS`

```bash
termux-sms-send -n "+5549912345678" "Mensagem enviada pelo Termux!"
```

---

## 👥 Contatos

**Permissão necessária:** `android.permission.READ_CONTACTS`

```bash
termux-contact-list
```

```json
[
  {
    "name": "Ana Clara",
    "number": "+554999786796"
  },
  {
    "name": "André Ghisleni Raimann",
    "number": "+554999383783"
  }
]
```

---

## 🔐 Biometria (Fingerprint)

```bash
termux-fingerprint -t "Autentique para continuar"
```

**Resposta sucesso:**
```json
{
  "errors": [],
  "failed_attempts": 0,
  "auth_result": "AUTH_RESULT_SUCCESS"
}
```

**Resposta falha:**
```json
{
  "errors": [],
  "failed_attempts": 1,
  "auth_result": "AUTH_RESULT_FAILURE"
}
```

---

## 🔔 Notificações

### Simples
```bash
termux-notification -t "Título" -c "Conteúdo da notificação"
```

### Com botões de ação
```bash
termux-notification \
  -t "Termux:API" \
  -c "Escolha uma ação:" \
  --button1 "Vibrar" \
  --button1-action "termux-vibrate -d 200" \
  --button2 "Lanterna" \
  --button2-action "termux-torch on;sleep 1;termux-torch off" \
  --button3 "Toast" \
  --button3-action "termux-toast 'Termux!'" \
  --alert-once
```

### Com imagem
```bash
termux-notification \
  -t "Foto" \
  -c "Selfie tirada" \
  --image-path /data/data/com.termux/files/home/selfie.jpg
```

### Remover notificação
```bash
termux-notification-remove -i <id>
```

### Listar notificações
```bash
termux-notification-list
```

---

## 💬 Diálogos

### Confirmação (Sim/Não)
```bash
termux-dialog confirm -t "Confirma" -i "Deseja continuar?"
# Saída: {"code": 0, "text": "yes"} ou {"code": 1, "text": "no"}
```

### Texto
```bash
termux-dialog text -t "Nome" -i "Digite seu nome:"
# Saída: {"code": 0, "text": "Gabriel"}
```

### Data
```bash
termux-dialog date -t "Escolha uma data"
# Saída: {"code": 0, "text": "2026-06-03"}
```

### Hora
```bash
termux-dialog time -t "Escolha um horário"
```

### Lista de opções (Radio)
```bash
termux-dialog radio -t "Escolha" -v "Opção 1,Opção 2,Opção 3"
```

### Múltipla escolha (Checkbox)
```bash
termux-dialog checkbox -t "Selecione" -v "A,B,C"
```

### Senha
```bash
termux-dialog password -t "Senha" -i "Digite:"
```

---

## 🍞 Toast

```bash
termux-toast "Mensagem rápida na tela!"
termux-toast -g top "No topo!"
termux-toast -g bottom "No rodapé!"
```

---

## 🖼️ Wallpaper (Papel de Parede)

```bash
# Da câmera
termux-camera-photo -c 1 ~/wallpaper.jpg
termux-wallpaper -f ~/wallpaper.jpg

# De URL
termux-wallpaper -u "https://exemplo.com/imagem.jpg"

# Tela de bloqueio
termux-wallpaper -l -f ~/wallpaper.jpg
```

---

## 📥 Download

```bash
# Download com notificação
termux-download -t "Título" -d "Descrição" https://exemplo.com/arquivo.zip

# Download silencioso
termux-download https://exemplo.com/arquivo.zip
```

---

## 🖼️ Media Scan (Galeria)

```bash
# Escanear arquivo para aparecer na galeria
termux-media-scan ~/storage/shared/foto.jpg

# Escanear múltiplos
termux-media-scan ~/storage/shared/foto1.jpg ~/storage/shared/foto2.jpg
```

---

## 🗓️ Job Scheduler (Agendamento)

```bash
#!/bin/sh
# Criar script
cat > ~/meu_job.sh << 'EOF'
#!/bin/sh
echo "$(date) - Job executado" >> ~/job_log.txt
termux-toast "Tarefa executada!"
EOF

chmod +x ~/meu_job.sh

# Agendar (mínimo 15 min no Android N+)
termux-job-scheduler -s ~/meu_job.sh --period-ms 900000

# Listar jobs pendentes
termux-job-scheduler -p

# Cancelar todos
termux-job-scheduler --cancel-all
```

> ⚠️ Android N+ impõe mínimo de 15 minutos (900000ms) para jobs periódicos.

---

## 📂 Storage Get (File Picker)

```bash
# Abre seletor de arquivos do Android
termux-storage-get ~/arquivo_selecionado.bin
```

---

## 🔌 USB OTG

```bash
# Listar dispositivos USB conectados
termux-usb -l

# Acessar dispositivo específico
termux-usb /dev/bus/usb/001/002
```

---

## 📡 NFC

```bash
# Ler tag (resumo)
termux-nfc -r short

# Ler tag (completo)
termux-nfc -r full

# Escrever texto em tag
termux-nfc -w -t "Texto para gravar na tag"
```

> ⚠️ **Limitado a tags NDEF.** Tags Mifare, ISO 15693, etc. retornam "Wrong Technology".

---

## 🗣️ Speech-to-Text

```bash
# Fala → texto
termux-speech-to-text
# Abre diálogo de reconhecimento de voz
```

**Permissão necessária:** `android.permission.RECORD_AUDIO`

---

## 💾 Keystore

```bash
# Listar chaves
termux-keystore list

# Gerar chave
termux-keystore generate -a "minha_chave" -p "senha"

# Assinar
termux-keystore sign -a "minha_chave" "dados para assinar"

# Verificar
termux-keystore verify -a "minha_chave" "dados" "assinatura"
```

---

## 📤 Compartilhar (Share)

```bash
# Compartilhar arquivo
termux-share -a send arquivo.jpg

# Compartilhar texto
termux-share -a send "Texto para compartilhar"
```

---

## 🔧 Comandos Úteis Combinados

### Script de status completo
```bash
#!/bin/sh
echo "=== STATUS DO DISPOSITIVO ==="
echo "🔋 Bateria: $(termux-battery-status | grep percentage | tr -dc '0-9')%"
echo "📶 WiFi: $(termux-wifi-connectioninfo | grep ssid | cut -d'"' -f4)"
echo "📍 GPS: $(termux-location | grep -E 'latitude|longitude' | head -2)"
echo "📱 Rede: $(termux-telephony-deviceinfo | grep network_operator_name | cut -d'"' -f4)"
```

### Monitor de bateria com alerta
```bash
#!/bin/sh
BAT=$(termux-battery-status | grep percentage | tr -dc '0-9')
if [ "$BAT" -lt 20 ]; then
  termux-notification -t "🔋 Bateria Baixa!" -c "${BAT}% restante" --alert-once
elif [ "$BAT" -eq 100 ]; then
  termux-notification -t "🔋 Bateria Cheia!" -c "Desconecte o carregador" --alert-once
fi
```

### Tirar foto e compartilhar
```bash
#!/bin/sh
termux-camera-photo -c 0 /tmp/foto.jpg
termux-share -a send /tmp/foto.jpg
```

---

## 🔑 Permissões Necessárias

| API | Permissão Android | Como conceder |
|---|---|---|
| GPS | `ACCESS_FINE_LOCATION` | Config → Apps → Termux:API → Permissões |
| Câmera | `CAMERA` | ↑ |
| Microfone | `RECORD_AUDIO` | ↑ |
| SMS (ler) | `READ_SMS` | ↑ |
| SMS (enviar) | `SEND_SMS` | ↑ |
| Contatos | `READ_CONTACTS` | ↑ |
| Telefone | `READ_PHONE_STATE` | ↑ |
| Call Log | `READ_CALL_LOG` | ↑ |
| Brilho | `WRITE_SETTINGS` | Config → Apps → Especial → Acesso de escrita |
| NFC | `NFC` | Já incluso |

---

## 📊 Resumo do Dispositivo

```
Dispositivo: Samsung Galaxy S23
Rede:        VIVO (MCC 724, MNC 6)
WiFi:        2NET_ALFF (78 Mbps)
IP Local:    10.0.0.35
Usuário:     u0_a471 (UID 10471)
Termux:API:  v0.59.1-1
Android:     API 27+ (Oreo ou superior)
```

---

## 🌐 SSH Remote Access

```bash
# Definir senha
passwd

# Iniciar servidor
sshd

# Conectar de outro dispositivo
ssh u0_a471@10.0.0.35 -p 8022

# Auto-iniciar com Termux
echo 'sshd 2>/dev/null' >> ~/.bashrc
```

---

**✅ Todas as APIs testadas e funcionando no Samsung Galaxy S23!**
