# OUTSCRAPER KEY — OWNER ACTION

> Ringkas. Satu-satunya langkah yang meng-unblock RUN_11. Jangan kirim key
> melalui Telegram/chat, jangan masukkan ke source code, jangan commit.

## 1. Akun & Key

1. Buka https://app.outscraper.com → daftar/login
2. Dashboard → API Keys → salin key (format `sk-...`)
3. Simpan key **langsung di server secara lokal** (langkah 2). Jangan kirim
   lewat chat/Telegram.

## 2. Pasang Key di Server (VPS 43.134.112.7)

```bash
cd /home/ubuntu/google-reviews-monitoring

umask 077

cat >> .env <<'EOF'
PUBLIC_REVIEW_PROVIDER=outscraper
OUTSCRAPER_API_KEY=<SET_LOCALLY_DO_NOT_SEND_IN_CHAT>
PUBLIC_REVIEW_TIMEOUT=30
PUBLIC_REVIEW_MAX_RETRIES=3
PUBLIC_REVIEW_PAGE_SIZE=50
PUBLIC_REVIEW_MAX_REVIEWS=100
EOF

chmod 600 .env
```

- File environment: `/home/ubuntu/google-reviews-monitoring/.env`
- Permission: `chmod 600 .env` (hanya owner yang baca)
- `.env` TIDAK tracked di git (sudah diverifikasi) — jangan `git add .env`

## 3. Verifikasi Tanpa Mencetak Nilai Key

```bash
cd /home/ubuntu/google-reviews-monitoring && python3 - <<'PY'
import os
from pathlib import Path

env_path = Path(".env")
assert env_path.exists(), ".env tidak ditemukan"

found = False
for line in env_path.read_text().splitlines():
    if line.startswith("OUTSCRAPER_API_KEY="):
        value = line.split("=", 1)[1].strip()
        found = bool(value and value != "<SET_LOCALLY_DO_NOT_SEND_IN_CHAT>")
        break

print("OUTSCRAPER_API_KEY configured:", found)
PY
```

Output harus `OUTSCRAPER_API_KEY configured: True`. Script ini hanya memeriksa
keberadaan, TIDAK mencetak nilai.

## 4. Restart Aplikasi (aman — PID-specific, TANPA broad pkill)

Deployment aktual: **tanpa systemd** — app GRM dijalankan via `venv/bin/python run.py`
pada port 8083. PID disimpan di `run/grm.pid` (folder `run/` sudah di-.gitignore).
Sebelum stop, PID diverifikasi benar-benar menjalankan repo GRM. JANGAN pakai
`pkill -f run.py` generik (bisa menghentikan proses Python lain).

```bash
cd /home/ubuntu/google-reviews-monitoring
mkdir -p run

# START (pertama kali / setelah rollback):
nohup venv/bin/python run.py > /tmp/grm-app.log 2>&1 &
echo $! > run/grm.pid

# RESTART aman:
if [ -f run/grm.pid ]; then
  PID=$(cat run/grm.pid)
  # Verifikasi PID benar-benar proses GRM (cmdline harus venv/bin/python run.py)
  if ps -p "$PID" -o cmd= 2>/dev/null | grep -q "venv/bin/python run.py"; then
    kill -TERM "$PID"
    for i in $(seq 1 10); do
      kill -0 "$PID" 2>/dev/null || break
      sleep 1
    done
    kill -0 "$PID" 2>/dev/null && kill -9 "$PID" 2>/dev/null || true
    echo "stopped $PID"
  else
    echo "PID $PID bukan proses GRM — tidak di-stop"
  fi
fi

nohup venv/bin/python run.py > /tmp/grm-app.log 2>&1 &
echo $! > run/grm.pid
sleep 3

# Health check port 8083
if curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8083/health | grep -q 200; then
  echo "health OK"
else
  echo "health FAILED — rollback ke mock, lihat langkah 6"
fi
```

Catatan: jangan menjalankan dua instance; cek `pgrep -af "venv/bin/python run.py"`
harus maksimal satu baris (tanpa wrapper bash).

## 5. Verifikasi Provider Aktif

Login via UI/API, lalu:
`GET /api/public/locations` → `configured_provider` harus `outscraper`

## 6. Rollback ke Mock

```bash
cd /home/ubuntu/google-reviews-monitoring
# ubah PUBLIC_REVIEW_PROVIDER=mock di .env (komentar baris outscraper/key)
sed -i 's/^PUBLIC_REVIEW_PROVIDER=outscraper/PUBLIC_REVIEW_PROVIDER=mock/' .env
# lalu restart aman dengan PID file (langkah 4)
```

Provider mock TIDAK membaca API key. Tidak ada silent fallback — perubahan
provider selalu eksplisit + restart. Jika health check gagal setelah aktivasi,
rollback ini adalah langkah pemulihan pertama.

## Setelah Key Terpasang

Lanjutkan RUN_11 yang sama (jangan RUN baru):
discovery nyata Bubur Fay → verifikasi Place ID asli (jangan pakai placeholder
`ChIJ0-depok-margonda-001`) → live sync 50–100 review → validasi manual ≥10
review → idempotency/incremental → dashboard/export → live audit record →
Gate L + regression B–L → update status RUN_11.
