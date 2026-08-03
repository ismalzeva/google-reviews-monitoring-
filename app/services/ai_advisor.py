"""AI Advisor — customer experience priorities (RUN_11).

Source of truth: skill `grm-apify-ai-advisor-deployment` §9–§11.

Focus: ONLY customer experience improvement. Output contract locked:

    Outlet | Masalah | Bukti | Saran Tindakan | PIC

- Max 3 issues per period (Top 3), priority Ringan/Sedang/Mendesak
- PIC taxonomy: Crew Outlet / Supervisor / Kitchen / Chef / Owner
- Evidence = review count + period + 1–3 short quotes; NEVER fabricated
- Rating-only reviews are NOT evidence for text categories
- Neutral language; no accusations; no root causes absent from data
- needs_human_review / confidence when evidence is weak
"""
import logging
from datetime import datetime, timezone

from app.models.entities import Review, ReviewAnalysis

logger = logging.getLogger(__name__)

# ─── ISSUE TEMPLATES (category → masalah + PIC + saran) ────
ISSUE_MAP = {
    "rasa/kualitas produk": {
        "masalah": "Rasa/kualitas produk tidak konsisten",
        "pic": "Kitchen / Chef",
        "saran": [
            "Lakukan quality check rasa sebelum disajikan.",
            "Standarisasi resep dan porsi di dapur.",
        ],
    },
    "pelayanan": {
        "masalah": "Pelayanan kurang ramah/cepat tanggap",
        "pic": "Crew Outlet",
        "saran": [
            "Ingatkan standar senyum-sapa-salam saat melayani.",
            "Adakan brief singkat standar pelayanan sebelum shift.",
        ],
    },
    "kecepatan/waktu tunggu": {
        "masalah": "Waktu tunggu order terlalu lama",
        "pic": "Supervisor",
        "saran": [
            "Telaah alur order di jam sibuk.",
            "Tambahkan personel di titik kritis bila perlu.",
        ],
    },
    "kebersihan": {
        "masalah": "Kebersihan tempat/dapur kurang",
        "pic": "Supervisor",
        "saran": [
            "Audit kebersihan area makan dan dapur.",
            "Perketat jadwal pembersihan harian.",
        ],
    },
    "harga": {
        "masalah": "Harga dinilai tidak sebanding",
        "pic": "Owner",
        "saran": [
            "Tinjau ulang strategi harga dan nilai produk.",
            "Komunikasikan nilai produk ke pelanggan.",
        ],
    },
    "porsi": {
        "masalah": "Porsi dinilai mengecil",
        "pic": "Kitchen / Chef",
        "saran": [
            "Standarisasi porsi setiap penyajian.",
            "Cek konsistensi porsi antar shift.",
        ],
    },
    "suasana/tempat": {
        "masalah": "Kenyamanan tempat kurang",
        "pic": "Supervisor",
        "saran": [
            "Periksa AC, pencahayaan, dan tata ruang.",
            "Rawat kebersihan dan kenyamanan area duduk.",
        ],
    },
    "parkir": {
        "masalah": "Akses/parkir menyulitkan pelanggan",
        "pic": "Supervisor",
        "saran": [
            "Koordinasi kelancaran parkir dengan petugas.",
            "Pasang penanda arah parkir yang jelas.",
        ],
    },
    "pesanan online/delivery": {
        "masalah": "Masalah pesanan online/delivery",
        "pic": "Supervisor",
        "saran": [
            "Perketat pengecekan pesanan sebelum dikirim.",
            "Perbaiki kemasan agar tidak bocor.",
        ],
    },
    "ketersediaan menu/stok": {
        "masalah": "Ketersediaan menu/stok tidak konsisten",
        "pic": "Kitchen / Chef",
        "saran": [
            "Perbaiki perencanaan stok bahan.",
            "Update ketersediaan menu secara rutin.",
        ],
    },
    "fasilitas": {
        "masalah": "Fasilitas pendukung kurang",
        "pic": "Supervisor",
        "saran": [
            "Evaluasi kelengkapan fasilitas pelanggan.",
            "Catat kebutuhan perbaikan fasilitas.",
        ],
    },
    "kritis": {
        "masalah": "Isu keamanan pangan/kesehatan",
        "pic": "Owner",
        "saran": [
            "Investigasi segera dengan tim terkait.",
            "Perketat SOP keamanan pangan dan kebersihan dapur.",
        ],
    },
}


def _now():
    return datetime.now(timezone.utc)


def _analysis(review) -> ReviewAnalysis:
    return ReviewAnalysis.query.filter_by(review_pk=review.id).first()


def _categories_for(review, analysis) -> list:
    from app.services.public_analytics import _categories_for as _cat
    return _cat(review, analysis)


def _sentiment(review, analysis) -> str:
    from app.services.public_analytics import _sentiment as _s
    return _s(review, analysis)


def _urgency(review, analysis) -> str:
    from app.services.public_analytics import _urgency as _u
    return _u(review, analysis)


def _quote(text, maxlen=110) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    if len(text) <= maxlen:
        return text
    return text[:maxlen].rsplit(" ", 1)[0] + "…"


def _priority_for(category: str, count: int, has_critical: bool, low_star_count: int) -> str:
    if has_critical or category == "kritis":
        return "Mendesak"
    if count >= 4 or low_star_count >= 3:
        return "Sedang"
    return "Ringan"


# ─── SPECIFIC SUB-ISSUE KEYWORDS (per kategori) ─────────────
# Granular, actionable breakdown: "Top Masalah Spesifik".
SUB_ISSUE_KEYWORDS = {
    "rasa/kualitas produk": [
        ("rasa berubah / tidak enak", ["rasa berubah", "tidak enak", "berbeda", "aneh", "hambar", "tawar", "asin", "kurang enak"]),
        ("makanan basi / tidak segar", ["basi", "busuk", "tengik", "kadaluarsa", "tidak segar", "layu", "dingin", "tidak hangat"]),
        ("topping / isi sedikit", ["topping", "toping", "isi sedikit", "ayam sedikit", "daging sedikit"]),
    ],
    "pelayanan": [
        ("tidak ramah / cuek", ["tidak ramah", "cuek", "judes", "kasar", "galak", "jarang senyum", "tidak senyum", "tidak sopan"]),
        ("tidak responsif / diabaikan", ["tidak respon", "diabaikan", "diam saja", "tidak dilayani", "dilayani lama"]),
        ("kasir / pelayan lambat", ["kasir lambat", "pelayan lambat", "lambat melayani"]),
    ],
    "kecepatan/waktu tunggu": [
        ("waktu tunggu lama", ["nunggu lama", "tunggu lama", "30 menit", "lama banget", "terlalu lama", "45 menit", "1 jam", "lama sekali"]),
        ("antre panjang", ["antre", "antri", "ngantri", "queue", "ramai banget"]),
    ],
    "kebersihan": [
        ("meja / area kotor", ["meja kotor", "meja lengket", "lantai kotor", "kotor"]),
        ("toilet kotor", ["toilet", "wc kotor", "kamar mandi"]),
        ("dapur tidak higienis", ["dapur kotor", "tidak higienis", "jijik"]),
    ],
    "harga": [
        ("harga naik / mahal", ["harga naik", "naik terus", "makin mahal", "kemahalan", "mahal"]),
        ("tidak sebanding", ["tidak sebanding", "tidak worth", "mahal untuk"]),
    ],
    "porsi": [
        ("porsi mengecil / sedikit", ["porsi kecil", "mengecil", "sedikit", "dikit", "makin kecil", "porsi dikit"]),
    ],
    "suasana/tempat": [
        ("AC tidak dingin / panas", ["ac tidak", "ac kurang", "panas", "gerah", "pengap", "tidak adem"]),
        ("tempat sempit / tidak nyaman", ["sempit", "sesak", "tidak nyaman"]),
    ],
    "pesanan online/delivery": [
        ("antar telat", ["telat", "lama sampai", "lama antar", "telat sampai"]),
        ("pesanan kurang / salah", ["kurang", "salah", "tidak lengkap", "lupa", "tidak sesuai"]),
        ("kemasan bocor / tumpah", ["bocor", "tumpah", "packing", "kemasan", "bungkus"]),
    ],
    "ketersediaan menu/stok": [
        ("menu / stok habis", ["habis", "kosong", "tidak ada", "out of stock", "stok", "tidak tersedia"]),
    ],
    "kritis": [
        ("keracunan / mual", ["mual", "muntah", "sakit perut", "keracunan", "diare", "sakit"]),
        ("benda asing", ["lalat", "ulat", "kecoa", "rambut", "belatung", "serangga"]),
    ],
}


def _extract_sub_issues(category: str, texts: list) -> list:
    """Break a category's complaint texts into specific, actionable sub-issues."""
    rules = SUB_ISSUE_KEYWORDS.get(category, [])
    if not rules:
        return []
    results = []
    for label, keywords in rules:
        count = 0
        example = ""
        for t in texts:
            tl = (t or "").lower()
            if any(k in tl for k in keywords):
                count += 1
                if not example:
                    example = t.strip()[:100]
        if count > 0:
            results.append({"masalah": label, "count": count, "contoh": example})
    results.sort(key=lambda x: x["count"], reverse=True)
    return results[:5]


def generate(tenant_id: str, business_id: str, filters: dict) -> dict:
    """Generate top customer-experience issues (max 3) for active filters."""
    from app.services import public_analytics as pa

    start, end, _, _ = pa._resolve_period(filters)
    rows = pa._base_reviews(tenant_id, business_id, filters, period=(start, end))

    # Aggregate issues per (outlet, category)
    issues = {}
    for review, outlet in rows:
        if not review.has_text:
            continue  # rating-only is NOT text-category evidence
        analysis = _analysis(review)
        sent = _sentiment(review, analysis)
        if sent not in ("negative", "mixed"):
            continue
        urg = _urgency(review, analysis)
        for cat in _categories_for(review, analysis):
            key = (outlet.id, cat)
            entry = issues.setdefault(key, {
                "outlet": outlet.name,
                "category": cat,
                "count": 0,
                "low_star_count": 0,
                "critical_count": 0,
                "ratings": [],
                "quotes": [],
                "texts": [],
                "period_start": start,
                "period_end": end,
                "sample_dates": [],
            })
            entry["count"] += 1
            entry["ratings"].append(review.star_rating)
            entry["texts"].append(review.comment or "")
            if review.star_rating <= 2:
                entry["low_star_count"] += 1
            if urg == "critical" or cat == "kritis":
                entry["critical_count"] += 1
            q = _quote(review.comment)
            if q and len(entry["quotes"]) < 3:
                entry["quotes"].append(q)
            if review.create_time:
                entry["sample_dates"].append(review.create_time.date().isoformat())

    if not issues:
        return {"issues": [], "generated_at": _now().isoformat()}

    # Score: count (weighted), low-star, critical
    scored = []
    for key, e in issues.items():
        template = ISSUE_MAP.get(e["category"], {
            "masalah": f"Masalah pada {e['category']}",
            "pic": "Supervisor",
            "saran": ["Tinjau ulang proses terkait kategori ini."],
        })
        score = e["count"] * 10 + e["low_star_count"] * 15 + e["critical_count"] * 25
        scored.append({
            "priority": _priority_for(e["category"], e["count"],
                                       e["critical_count"] > 0, e["low_star_count"]),
            "outlet": e["outlet"],
            "masalah": template["masalah"],
            "bukti": {
                "review_count": e["count"],
                "period": f"{e['period_start'].date().isoformat()} s/d {e['period_end'].date().isoformat()}",
                "quotes": e["quotes"],
                "low_star_count": e["low_star_count"],
                "critical_count": e["critical_count"],
            },
            "saran_tindakan": template["saran"][:3],
            "pic": template["pic"],
            "status": "Open",
            "created_at": _now().isoformat(),
            "score": score,
            "confidence": "rendah" if e["count"] < 3 else ("sedang" if e["count"] < 6 else "tinggi"),
            "needs_human_review": e["count"] < 2 or e["critical_count"] > 0,
        })

    scored.sort(key=lambda x: ({"Mendesak": 0, "Sedang": 1, "Ringan": 2}[x["priority"]], -x["score"]))
    top = scored[:3]

    # Neutralize language: strip any accidental accusation phrasing
    for issue in top:
        issue.pop("score", None)
        # Top Masalah Spesifik: granular sub-issue breakdown from complaint texts
        key_match = None
        for (oid, cat), e in issues.items():
            if e["outlet"] == issue["outlet"] and ISSUE_MAP.get(cat, {}).get("masalah") == issue["masalah"]:
                key_match = e
                break
        if key_match:
            issue["sub_issues"] = _extract_sub_issues(key_match["category"], key_match["texts"])

    return {"issues": top, "generated_at": _now().isoformat()}
