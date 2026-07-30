---
name: branch-discovery-and-verification
version: 1.0.0
type: location-discovery-skill
status: active
---

# HERMES AGENT SKILL — BRANCH DISCOVERY & VERIFICATION

## 1. PURPOSE

Memungkinkan owner mengetik nama brand seperti `Bubur Fay`, lalu sistem mencari kandidat titik bisnis dan meminta owner memverifikasi mana cabang yang benar.

## 2. CRITICAL RULE

Hasil Google Places Text Search adalah **public discovery candidate**.

Hasil tersebut:

- tidak membuktikan kepemilikan;
- tidak otomatis memberi akses pengelolaan;
- tidak boleh langsung dipakai untuk memublikasikan balasan;
- harus diverifikasi owner dan direkonsiliasi dengan akun Google Business Profile.

## 3. REQUIRED INPUT

```yaml
business_name: "Bubur Fay"
search_region:
  country: "Indonesia"
  province: optional
  city: optional
search_language: "id"
```

Minimal input adalah `business_name`.

## 4. DISCOVERY QUERY STRATEGY

### Query Utama

```text
Bubur Fay
```

### Query Lokasi

Jika area diketahui:

```text
Bubur Fay Depok
Bubur Fay Bekasi
Bubur Fay Jakarta
```

### Refinement

Gunakan:

- location bias;
- Bahasa Indonesia;
- business/place fields yang dibutuhkan;
- pagination sampai batas hasil API.

Jangan melakukan query berulang tanpa deduplication.

## 5. REQUESTED PLACE FIELDS

Minimal:

- `places.id`;
- `places.displayName`;
- `places.formattedAddress`;
- `places.location`;
- `places.businessStatus`;
- `places.googleMapsUri`;
- `places.rating`;
- `places.userRatingCount`;
- `places.primaryType`;
- `places.nationalPhoneNumber`;
- `places.websiteUri`.

Gunakan field mask minimum untuk mengendalikan biaya dan data.

## 6. NORMALIZED CANDIDATE

```yaml
candidate_id:
business_id:
search_query:
place_id:
display_name:
formatted_address:
latitude:
longitude:
business_status:
google_maps_uri:
rating:
review_count:
phone:
website:
source: google_places_text_search
discovery_status: discovered
match_confidence:
match_reasons: []
owner_verification_status: pending
created_at:
```

## 7. CANDIDATE MATCH SCORING

Scoring boleh menggunakan:

- kesamaan nama;
- kecocokan kota;
- kecocokan alamat;
- kecocokan telepon;
- kecocokan website;
- jarak dengan area operasi;
- place ID;
- status bisnis;
- kecocokan dengan lokasi akun resmi.

Scoring tidak menggantikan verifikasi owner.

## 8. DEDUPLICATION

Kandidat dianggap kemungkinan duplikat apabila:

- `place_id` sama; atau
- nama sangat mirip dan koordinat sangat dekat; atau
- alamat dan telepon sama; atau
- hasil beberapa query menunjuk lokasi yang sama.

Simpan satu canonical candidate dan daftar discovery aliases.

## 9. OWNER VERIFICATION UI

Setiap kandidat wajib menampilkan:

- nama;
- alamat;
- peta;
- rating;
- jumlah review;
- status buka/tutup;
- Google Maps link;
- telepon/website jika tersedia.

Owner memilih:

- `Ini cabang Bubur Fay`
- `Bukan cabang Bubur Fay`
- `Cabang lama/sudah tutup`
- `Listing duplikat`
- `Belum yakin`
- `Perlu diklaim atau diperiksa`

Normalized values:

```yaml
owner_confirmed
owner_rejected
old_or_closed
possible_duplicate
uncertain
needs_access_review
```

## 10. OWNER VERIFICATION RECORD

```yaml
verification_id:
candidate_id:
decision:
verified_by_user_id:
verification_note:
verified_at:
```

Keputusan owner harus dapat diaudit dan diperbarui oleh pengguna berwenang.

## 11. RECONCILIATION WITH GBP

Setelah akun Google terhubung:

1. Ambil accessible official locations.
2. Ambil `metadata.place_id` bila tersedia.
3. Match exact Place ID terlebih dahulu.
4. Jika Place ID tidak tersedia, gunakan nama, alamat, telepon, dan koordinat.
5. Tandai hasil:

```yaml
matched_to_gbp
unmatched_to_gbp
ambiguous_match
```

## 12. LOCATION MATRIX OUTPUT

```yaml
brand: Bubur Fay
candidates:
  - public_candidate:
      place_id:
      name:
      address:
    owner_decision:
    gbp_match:
      account_id:
      location_id:
      match_status:
      permission_status:
    management_status:
      monitor_enabled:
      reply_enabled:
```

## 13. MANAGEMENT PERMISSION RULE

`reply_enabled` hanya boleh `true` apabila:

- akun Google terhubung;
- user memiliki scope yang diperlukan;
- location berada dalam accessible locations;
- location memenuhi syarat API review;
- quality gate koneksi lulus.

## 14. FAILURE STATES

- `no_candidates_found`
- `places_api_not_configured`
- `quota_exceeded`
- `ambiguous_brand_name`
- `owner_verification_pending`
- `gbp_connection_required`
- `official_location_not_found`
- `location_not_manageable`

## 15. ACCEPTANCE CRITERIA

- Query `Bubur Fay` menghasilkan daftar kandidat atau alasan valid mengapa tidak.
- Kandidat tidak otomatis menjadi official outlet.
- Owner dapat memverifikasi setiap kandidat.
- Duplicate candidates tidak ditampilkan sebagai cabang terpisah tanpa penanda.
- Setelah OAuth, sistem dapat menampilkan hasil rekonsiliasi.
- Hanya official/manageable location yang dapat mengaktifkan reply.
