# SE Havacılık · MTConnect Dashboard (5 Machines)

Browser tabanlı, real-time fleet dashboard. Beş Haas tezgahını eş zamanlı izler:

| ID       | Machine    | Type    | Notes                                               |
|----------|------------|---------|-----------------------------------------------------|
| `vf6`    | VF-6/40    | mill    | 3-axis, full data                                   |
| `vf4`    | VF-4       | mill    | 3-axis, currently offline                           |
| `umc400` | UMC-400    | mill    | 5-axis (X/Y/Z + B/C), full load                     |
| `umc750` | UMC-750    | mill    | 5-axis (X/Y/Z + B/C), no axis loads (eski firmware) |
| `st10`   | ST-10      | lathe   | 2-axis (X/Z), lathe tool offsets                    |

Hostlar / IP'ler `machines.json` dosyasında — repoya commit edilmez (gitignore).

## Hızlı başlangıç

```bash
# 1) Makina listesini hazırla (host IP'lerini gir)
cp machines.example.json machines.json
$EDITOR machines.json

# 2) Sunucuyu başlat (server.py + dashboard.html + machines.json aynı klasörde)
python3 server.py
```

Browser: **http://localhost:8000**

## Per-machine davranış

Probe'lardan tespit edilen makinaya özgü farklılıklar:

**ST-10 (Lathe)**
Tool DataItem ID'leri tamamen farklı: `toolidlathe`, `xgeometry`/`xwear`, `zgeometry`/`zwear`, `diamgeolathe`/`diamwearlathe`, `tip`, `taper`, `pocketlathe`. Dashboard `type: "lathe"` görünce tool kartını otomatik bu alanlarla render eder. Pozisyon kartı sadece X ve Z gösterir (Y eksiği probe'da yok). Mor (`--lathe`) accent rengi, mill'lerden ayırt etmek için.

**UMC-750 (Eski firmware)**
Firmware: REL-100.24.000 (diğerleri 100.25). Bu sürümde `*_axis_load` DataItem'leri publish edilmiyor. Dashboard "No axis load data published" mesajı gösterir, çökmez. Pozisyon ve diğer her şey normal çalışır. Firmware yükseltilirse otomatik dolar.

**UMC-400 (Tam 5-axis)**
B (tilt) ve C (rotation) eksenleri linear axes ile aynı yapıda publish ediliyor. Pozisyonda mavi etiketle "DEG" birimi gösterilir. Load barları da B ve C için var.

**VF-4 (Offline)**
IP'ye ulaşılamadığında summary card'da kırmızı dot, "OFFLINE" etiketi ve hata mesajı görünür. Diğer makinaların poll cycle'ı etkilenmez (`Promise.allSettled` paralel).

## Layout

```
┌────────────────────────────────────────────────────────────────────────┐
│ Header · fleet özet (3 ACTIVE · 1 IDLE · 1 OFFLINE)         clock      │
├────────────┬────────────┬────────────┬────────────┬────────────┐      │
│ ● VF-6/40  │ ● VF-4     │ ● UMC-400  │ ● UMC-750  │ ● ST-10    │      │
│   ACTIVE   │   OFFLINE  │   READY    │   ACTIVE   │   READY    │      │
│   T07/RPM  │   —        │   T—/0     │   T12/3500 │   T05/2000 │      │
│   ...      │   ...      │   ...      │   ...      │   ...      │      │
├────────────┴────────────┴────────────┴────────────┴────────────┘      │
│  ─── DETAIL VIEW · UMC-400 · MILL ─────────────────                    │
│  [Status] [Spindle] [Program] [Counters]                               │
│  [Overrides bars]  [Axis loads X/Y/Z/B/C dynamic]                      │
│  [Position X/Y/Z mm + B/C deg]  [Tool] [Cycle]                         │
│  [Macros + active codes]  [Work offsets]                               │
│  [Active alarms + event log]                                           │
└────────────────────────────────────────────────────────────────────────┘
```

Üst stripte 5 makina daima görünür, kart aralığı 1 saniyede paralel güncellenir. Bir karta tıklayınca alttaki detay panel ona geçer (seçim `localStorage`'da kalıyor). Fleet özeti header'da: aktif/idle/offline/alarm sayaçları.

## Konfigürasyon

Makina listesi `machines.json` dosyasında — her makina için:

```json
"machine_id": {
  "name":  "Display name",
  "model": "Description",
  "host":  "<machine-host-or-ip>",
  "port":  8082,
  "type":  "mill"
}
```

`type` alanı `"mill"` veya `"lathe"` — tool DataItem'lerini seçiyor.

Yeni makina eklemek için tek yapman gereken bu dosyaya satır eklemek — dashboard `/api/machines`'i otomatik okur, kart oluşturur. Server restart yeterli.

`machines.example.json` repoda kalır (placeholder IP'lerle, TEST-NET-1 `192.0.2.x` aralığı). Gerçek `machines.json` `.gitignore`'da — public repoya host bilgisi sızmaz.

## Routing

| Path                          | Behavior                                        |
|-------------------------------|------------------------------------------------|
| `GET /`                       | dashboard.html                                  |
| `GET /api/machines`           | JSON: `[{id, name, model, type}, ...]`          |
| `GET /mtc/<id>/current`       | → `http://<host>:<port>/current`                |
| `GET /mtc/<id>/probe`         | → `http://<host>:<port>/probe`                  |
| `GET /mtc/<id>/sample?...`    | Query string da forward edilir (long-poll için) |

Timeout: 5 saniye. Offline makinalar hızlı 502 döndürür, dashboard'u yavaşlatmaz.

## Veri kaynakları (probe'lardan tespit edilen)

Hepsinin ortak (mill + lathe):
- `rstat` (EXECUTION), `mode` (CONTROLLER_MODE), `estop`, `avail`
- `sspeed`, `ssovrd`, `fdovrd`, `rovrd`
- `tcycle`, `lcycle`, `cyremtim`, `machineruntime`, `spindletime`
- `m30c1`, `m30c2`, `lpremain`, `ncprog`
- `gcodes`, `dhmtcodes`, `addresscodes`
- `aalarms`, `elog`, `mcond`
- `macdsp1`, `macdsp2` (configurable Haas tarafından)
- Work offsets G54..G59, G92, G154

Mill'e özel: `toolid`, `lengthgeo`, `lengthwear`, `diamgeo`, `diamwear`, `pocket`
Lathe'e özel: `toolidlathe`, `xgeometry`/`xwear`, `zgeometry`/`zwear`, `diamgeolathe`/`diamwearlathe`, `tip`, `taper`, `pocketlathe`

## Shop-Floor TV Mode

Büyük ekranda fabrika girişine asmak için: URL'ye `?mode=tv` ekle.

```
http://<server>:8000/?mode=tv
```

TV mode'da:
- Header, detay paneli, section divider tamamen gizlenir
- 5 makina kartı tam ekrana yayılır (5-up grid, 1920×1080'de yan yana sığar)
- Font'lar `clamp()` ile ekran boyutuna göre büyür (exec status 40-68px arası)
- Kart tıklamaları devre dışı (kiosk mode)
- Sağ alt köşede kalıcı clock + fleet özeti
- 1500px altı ekranlarda otomatik 3-up'a, 900px altı 2-up'a düşer (portrait monitor desteği)
- Açılışta 5 saniyelik "press F for fullscreen" hint'i; ESC normal çıkış

Klavye:
- `F` → fullscreen aç/kapat
- `ESC` → fullscreen'den çık (browser native)

Kiosk için Chrome bayrakları:
```bash
google-chrome \
  --kiosk \
  --noerrdialogs \
  --disable-translate \
  --no-first-run \
  --start-fullscreen \
  --incognito \
  http://localhost:8000/?mode=tv
```

Veya Raspberry Pi'de Chromium ile aynı bayraklar; Pi'yi shop floor TV'ye HDMI'la bağla, autostart'a koy.

## Sonraki adımlar

1. **Macro display map'leri**  — Her tezgahın Haas tarafında `macdsp1`/`macdsp2` makro değişken bağlantılarını yap:
   - Önerilen: `macdsp1` → spindle load (#3027 veya equivalent), `macdsp2` → actual feedrate
   - ST-10 için: turret index, sub-spindle load, vb.

2. **TimescaleDB persistence** — `server.py`'a writer ekle, her başarılı poll DB'ye düşsün:
   - `samples` tablosu (machine_id, dataitem_id, timestamp, numeric_value)
   - `events` tablosu (machine_id, dataitem_id, timestamp, value)
   - `alarms` tablosu (machine_id, code, severity, message, started_at, ended_at)
   - 7 gün raw, 30 gün 1-sn aggregate, sonsuz 1-dk aggregate retention

3. **Long-poll streaming** — `/sample?from=<seq>&interval=200` ile sequence-aware streaming. 1 sn altı event'leri yakalar (kısa FEED_HOLD, alarm flap'leri).

4. **OEE rolling window** — Server tarafında availability/performance/quality hesapla, dashboard'da gauge olarak göster.

5. **Probe-driven schema** — Startup'ta her makinanın `/probe`'unu çekip available DataItem'leri tespit et. UMC-750 firmware'i yükselince otomatik load gösterir.

## Production deployment

```ini
# /etc/systemd/system/se-mtc-dashboard.service
[Unit]
Description=SE Havacılık MTConnect Dashboard
After=network.target

[Service]
Type=simple
User=mtconnect
WorkingDirectory=/opt/mtc-dashboard
ExecStart=/usr/bin/python3 /opt/mtc-dashboard/server.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Veya Docker:
```dockerfile
FROM python:3.12-alpine
WORKDIR /app
COPY server.py dashboard.html ./
EXPOSE 8000
CMD ["python3", "-u", "server.py"]
```

## Bilinen kısıtlamalar

- **Spindle load**: native DataItem değil. `macdsp1` map'le.
- **Path feedrate (mm/dak gerçek)**: native değil, sadece override %. `macdsp2` map'le.
- **Door state**: native değil.
- **`/asset` endpoint**: assetCount=0 — tüm tool table senkronu MTConnect üzerinden mümkün değil. Net Share kullan.
- **UMC-750 axis loads**: Firmware 100.24'te yok. Yükseltilirse otomatik dolar.
- **VF-4**: Şu an offline, IP doğru ayarlı; tezgah açıldığında otomatik bağlanır.
