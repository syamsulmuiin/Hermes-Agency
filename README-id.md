<p align="center">
  <img src="https://img.shields.io/badge/HERMES-AGENCY-FF6B35?style=for-the-badge&logo=hermes&logoColor=white" alt="Hermes Agency"/>
</p>

<h1 align="center">Hermes Agency</h1>

<p align="center">
  <strong>Template System Prompt Multi-Agent AI</strong><br>
  <em>Bangun agen AI terstruktur dengan peran agen, aturan bersama, dan pola workflow yang terbukti.</em>
</p>

<p align="center">
  <a href="#fitur">Fitur</a> •
  <a href="#mulai-cepat">Mulai Cepat</a> •
  <a href="#peran-agen">Agen</a> •
  <a href="#panduan-setup">Setup</a> •
  <a href="README.md">English</a> •
  <a href="#lisensi">Lisensi</a>
</p>

---

<p align="center">
  <img src="https://img.shields.io/badge/Lisensi-MIT-hijau?style=flat-square" alt="Lisensi"/>
  <img src="https://img.shields.io/badge/Agen-6-biru?style=flat-square" alt="Agen"/>
  <img src="https://img.shields.io/badge/LLM-Semua-ungu?style=flat-square" alt="LLM"/>
  <img src="https://img.shields.io/badge/Platform-Universal-oranye?style=flat-square" alt="Platform"/>
</p>

---

## Apa itu Hermes Agency?

Hermes Agency adalah **template system prompt** yang mengubah LLM apa pun menjadi tim multi-agent terstruktur. Template ini menyediakan peran agen khusus, aturan governansi, dan pola workflow untuk membangun agen AI.

**Tidak perlu kode.** Cukup salin prompt ke platform LLM favorit Anda.

### Mengapa Menggunakan Ini?

| Masalah | Solusi |
|---------|--------|
| AI tunggal kurang spesialisasi | 6 peran agen khusus |
| Agen bekerja secara terisolasi | Aturan bersama memastikan kolaborasi |
| Tidak ada workflow jelas | Pola handoff yang terbukti disertakan |
| Ketergantungan platform | Bekerja dengan penyedia LLM apa pun |
| Mulai dari nol | Template siap produksi |

---

## Fitur

- **6 Agen Khusus** — CEO, PM, Peneliti, Pengembang, Desainer, QA
- **Aturan Governansi Bersama** — Koordinasi lintas agen dan resolusi konflik
- **Arsitektur Thread** — Konteks terisolasi dengan handoff terstruktur
- **Template Platform** — Panduan setup untuk ChatGPT, Claude, Cursor, dan API kustom
- **Contoh Nyata** — Workflow proyek lengkap dari klien hingga deployment
- **Semua Penyedia LLM** — OpenAI, Anthropic, Google, Mistral, model lokal

---

## Mulai Cepat

### 1. Clone atau Download

```bash
git clone https://github.com/syamsulmuiin/Hermes-Agency.git
cd Hermes-Agency
```

### 2. Pilih Platform Anda

| Platform | Panduan |
|----------|---------|
| ChatGPT | [chatgpt-setup.md](templates/chatgpt-setup.md) |
| Claude | [claude-setup.md](templates/claude-setup.md) |
| Cursor IDE | [cursor-setup.md](templates/cursor-setup.md) |
| API LLM Kustom | [custom-llm-setup.md](templates/custom-llm-setup.md) |

### 3. Salin Prompt

Setiap agen memiliki system prompt di folder `prompts/`. Salin konten ke field system instruction LLM Anda.

### 4. Mulai Membangun

1. Mulai dengan **Agen CEO** — bagikan persyaratan klien Anda
2. Teruskan output ke agen **Peneliti** dan **PM**
3. Lanjutkan workflow melalui **Desainer** → **Pengembang** → **QA**

---

## Peran Agen

| Agen | Thread ID | Tanggung Jawab | Output |
|------|-----------|----------------|--------|
| **CEO** | 1 | Komunikasi klien, persyaratan | Project Brief |
| **Project Manager** | 3 | Perencanaan eksekusi, koordinasi | Technical Design Document |
| **Desainer** | 4 | Desain UI/UX, mockup | Design System, Wireframe |
| **Pengembang** | 6 | Implementasi kode | Source Code, Test |
| **Peneliti** | 7 | Riset teknologi | Research Report, Rekomendasi |
| **QA** | 8 | Jaminan kualitas | Test Report, Bug Report |

### Peta Ketergantungan Agen

```
Klien
   ↓
Agen CEO
   ↓
Agen PM ←→ Agen Peneliti
   ↓              ↓
Agen Desainer     ↓
   ↓              ↓
Agen Pengembang ←┘
   ↓
Agen QA
   ↓
Deployment
```

---

## Struktur Repositori

```
Hermes-Agency/
├── README.md                          # File ini (English)
├── README-id.md                       # Versi Indonesia
├── LICENSE                            # Lisensi MIT
│
├── prompts/                           # System prompt untuk setiap agen
│   ├── 01-ceo-agent.md
│   ├── 02-project-manager-agent.md
│   ├── 03-researcher-agent.md
│   ├── 04-developer-agent.md
│   ├── 05-designer-agent.md
│   ├── 06-qa-agent.md
│   └── shared-rules.md                # Aturan governansi multi-agent
│
├── templates/                         # Panduan setup per platform
│   ├── chatgpt-setup.md
│   ├── claude-setup.md
│   ├── cursor-setup.md
│   ├── custom-llm-setup.md
│   └── thread-architecture.md
│
├── examples/                          # Contoh penggunaan nyata
│   ├── client-project-example.md
│   └── agent-handoff-example.md
│
└── assets/                            # Diagram dan referensi
    └── architecture-diagram.md
```

---

## Panduan Setup

### ChatGPT
Buat Custom GPT terpisah untuk setiap agen. Salin system prompt ke instruksi GPT.

[Lihat Panduan ChatGPT →](templates/chatgpt-setup.md)

### Claude
Gunakan Claude Projects untuk setiap agen. Tambahkan aturan bersama ke instruksi setiap proyek.

[Lihat Panduan Claude →](templates/claude-setup.md)

### Cursor IDE
Gunakan direktori `.cursor/rules/` dengan file instruksi khusus agen.

[Lihat Panduan Cursor →](templates/cursor-setup.md)

### API LLM Kustom
Wrapper Python untuk penyedia LLM apa pun (OpenAI, Anthropic, Google, Mistral, model lokal).

[Lihat Panduan Kustom →](templates/custom-llm-setup.md)

---

## Arsitektur Thread

Setiap agen beroperasi dalam thread (konteks percakapan) sendiri. Thread terhubung melalui handoff terstruktur.

| Agen | Thread ID | Membaca Dari |
|------|-----------|-------------|
| CEO | 1 | Klien |
| PM | 3 | Thread 1, Thread 7 |
| Desainer | 4 | Thread 1, Thread 3 |
| Pengembang | 6 | Thread 1, Thread 3, Thread 4 |
| Peneliti | 7 | Thread 1 |
| QA | 8 | Thread 1, Thread 3, Thread 6 |

[Lihat Panduan Thread Lengkap →](templates/thread-architecture.md)

---

## Contoh

### Workflow Proyek Lengkap
Lihat bagaimana proyek website restoran mengalir melalui semua 6 agen, dari permintaan klien hingga deployment.

[Lihat Contoh Proyek →](examples/client-project-example.md)

### Pola Handoff Agen
Pelajari format pasti untuk meneruskan pekerjaan antar agen dengan handoff terstruktur.

[Lihat Contoh Handoff →](examples/agent-handoff-example.md)

---

## Aturan Bersama

Aturan bersama memastikan semua agen bekerja sama secara kohesif:

1. **Baca Sebelum Tulis** — Selalu baca thread yang relevan sebelum memulai
2. **Hormati Batasan** — Tetap di jalur Anda, jangan ubah pekerjaan orang lain
3. **Jangan Mengarang** — Jangan buat informasi yang hilang, mintalah
4. **Output Terstruktur** — Jaga output tetap bersih untuk agen berikutnya
5. **Sumber Kebenaran** — Perlakukan dokumen agen lain sebagai otoritatif

[Lihat Aturan Lengkap →](prompts/shared-rules.md)

---

## Berkontribusi

Kontribusi diterima! Silakan:

- Tambahkan peran agen baru
- Tingkatkan prompt yang ada
- Tambahkan panduan setup untuk platform baru
- Bagikan contoh workflow Anda

1. Fork repositori
2. Buat branch fitur Anda (`git checkout -b feature/fitur-luar biasa`)
3. Commit perubahan Anda (`git commit -m 'Tambah fitur luar biasa'`)
4. Push ke branch (`git push origin feature/fitur-luar biasa`)
5. Buka Pull Request

---

## Lisensi

Proyek ini dilisensikan di bawah Lisensi MIT — lihat file [LICENSE](LICENSE) untuk detail.

---

## Penghargaan

- Terinspirasi oleh framework multi-agent: CrewAI, LangGraph, AutoGen
- Pola system prompt dari [awesome-ai-system-prompts](https://github.com/dontriskit/awesome-ai-system-prompts)
- Dibuat dengan cinta untuk komunitas agen AI

---

<p align="center">
  <strong>Dibuat oleh <a href="https://github.com/malvinjauhari">Malvin Jauhari</a></strong>
</p>
