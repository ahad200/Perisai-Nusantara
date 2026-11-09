"""Klien Sovereign LLM (PRD §6 F2, FR-404).

Dua implementasi:
- `StubLlm` (default): deterministik, OFFLINE, tanpa jaringan. Menyusun jawaban
  JSON valid langsung dari `AgentContext` terstruktur — mengabaikan teks prompt
  (tempat injeksi biasa muncul), jadi tahan prompt injection secara bawaan. Etos
  sama dengan "semua adapter mock" (§A.5 no.8).
- `OllamaLlm`: LLM lokal open-weight via HTTP. **Egress guard**: hanya loopback
  diizinkan (air-gapped, §A.5 no.5 / FR-404). Host non-lokal → ditolak saat init.

Keduanya mengembalikan STRING JSON mentah; pemanggil memvalidasinya dengan skema
Pydantic (lihat `agents/schemas.py`) sebelum dipakai.
"""
from __future__ import annotations

import json
import urllib.request
from ipaddress import ip_address
from typing import Protocol
from urllib.parse import urlsplit

from app.agents.sandbox import AgentContext, ContextItem

_LOOPBACK_HOSTNAMES = {"localhost", "127.0.0.1", "::1", ""}


class LlmError(RuntimeError):
    pass


class LlmClient(Protocol):
    name: str

    def generate(self, task: str, prompt: str, ctx: AgentContext) -> str: ...


# --------------------------------------------------------------------------- #
# Egress guard                                                                #
# --------------------------------------------------------------------------- #
def assert_loopback(base_url: str) -> None:
    """Pastikan URL LLM menunjuk ke loopback. Menolak egress keluar (FR-404)."""
    host = urlsplit(base_url).hostname or ""
    if host in _LOOPBACK_HOSTNAMES:
        return
    try:
        if ip_address(host).is_loopback:
            return
    except ValueError:
        pass
    raise LlmError(
        f"LLM base_url harus loopback (air-gapped, §A.5 no.5). Ditolak: {host!r}"
    )


# --------------------------------------------------------------------------- #
# Stub deterministik (default)                                                #
# --------------------------------------------------------------------------- #
class StubLlm:
    name = "stub-sovereign"

    def generate(self, task: str, prompt: str, ctx: AgentContext) -> str:
        if task == "attribution":
            return json.dumps(_stub_attribution(ctx))
        if task == "summary":
            return json.dumps(_stub_summary(ctx))
        if task == "hunt":
            return json.dumps(_stub_hunt(ctx))
        raise LlmError(f"task tak dikenal: {task}")


def _items_for(ctx: AgentContext, technique: str) -> list[ContextItem]:
    return [it for it in ctx.items if it.technique == technique]


def _refs_for(ctx: AgentContext, technique: str) -> list[str]:
    return [it.ref for it in _items_for(ctx, technique)]


def _any_refs(ctx: AgentContext, limit: int = 3) -> list[str]:
    return [it.ref for it in ctx.items[:limit]]


# Hipotesis atribusi berbasis kombinasi teknik (deterministik, konservatif).
def _stub_attribution(ctx: AgentContext) -> dict:
    tq = set(ctx.techniques)
    evidence: list[dict] = []
    alternatives: list[str] = []

    def ev(technique: str, text: str) -> None:
        refs = _refs_for(ctx, technique)
        if refs:
            evidence.append({"text": text, "refs": refs})

    if "T1486" in tq:
        actor = "Kelompok ransomware (motif dampak/kriminal)"
        confidence = "medium"
        ev("T1486", "Enkripsi data untuk dampak (T1486) terdeteksi pada host target.")
        alternatives = ["Operasi destruktif bersponsor negara menyamar sebagai ransomware", "Insider dengan akses tinggi"]
    elif "T1110" in tq and "T1071" in tq:
        actor = "Aktor persisten (APT) — akses kredensial lalu kanal C2"
        confidence = "medium"
        ev("T1110", "Brute force kredensial (T1110) mendahului komunikasi C2.")
        ev("T1071", "Kanal C2 lapisan aplikasi (T1071) aktif pasca-kompromi.")
        alternatives = ["Kampanye kriminal komoditas (botnet)", "Pengujian keamanan internal yang tak terkoordinasi"]
    elif "T1110" in tq:
        actor = "Aktor oportunistik — percobaan brute force kredensial"
        confidence = "low"
        ev("T1110", "Lonjakan kegagalan autentikasi khas brute force (T1110).")
        alternatives = ["Kesalahan konfigurasi akun sah (bukan serangan)", "Credential stuffing dari botnet"]
    elif "T1071" in tq:
        actor = "Kanal C2 aktif — kemungkinan malware ter-beacon"
        confidence = "low"
        ev("T1071", "Pola beaconing periodik ke luar (T1071).")
        alternatives = ["Perangkat lunak sah yang beaconing (false positive)", "Tunneling data oleh insider"]
    elif "T1595" in tq:
        actor = "Pengintaian/pemindaian — pelaku belum teridentifikasi"
        confidence = "low"
        ev("T1595", "Aktivitas pemindaian aktif (T1595).")
        alternatives = ["Pemindai kerentanan internal terjadwal", "Mesin pencari/crawler publik"]
    else:
        actor = "Belum cukup bukti untuk atribusi"
        confidence = "low"
        alternatives = ["Perlu pengumpulan bukti tambahan"]
        if ctx.items:
            evidence.append({"text": "Bukti terbatas; atribusi ditahan.", "refs": _any_refs(ctx)})

    return {
        "actor": actor,
        "confidence": confidence,
        "evidence": evidence,
        "alternatives": alternatives,
        "rationale": (
            "Hipotesis disusun dari kombinasi teknik ATT&CK yang teramati; "
            "severity final tetap dari rule engine, bukan dari model. Wajib divalidasi TI Officer."
        ),
    }


def _stub_summary(ctx: AgentContext) -> dict:
    findings: list[dict] = []
    for tech in ctx.techniques:
        refs = _refs_for(ctx, tech)
        if refs:
            findings.append({"text": f"Aktivitas teknik {tech} teramati.", "refs": refs})
    steps: list[str] = []
    tq = set(ctx.techniques)
    if "T1486" in tq:
        steps.append("Isolasi host terdampak dan tinjau cadangan untuk pemulihan.")
    if "T1110" in tq:
        steps.append("Reset kredensial akun terdampak dan aktifkan MFA.")
    if "T1071" in tq:
        steps.append("Blokir tujuan C2 dan periksa host lain dengan pola serupa.")
    if not steps:
        steps.append("Kumpulkan bukti tambahan dan tinjau linimasa insiden.")
    confidence = "medium" if len(ctx.techniques) >= 2 else "low"
    return {
        "summary": (
            f"Insiden {ctx.incident_code} pada host {ctx.host or '-'} "
            f"(severity {ctx.severity}) melibatkan teknik: {', '.join(ctx.techniques) or '-'}."
        ),
        "key_findings": findings,
        "recommended_next_steps": steps,
        "confidence": confidence,
    }


def _stub_hunt(ctx: AgentContext) -> dict:
    queries: list[dict] = []
    tq = set(ctx.techniques)
    if "T1110" in tq:
        queries.append({"description": "Cari akun lain dengan lonjakan kegagalan autentikasi.",
                        "filter": "category=authentication outcome=failure | stats by user", "refs": _refs_for(ctx, "T1110")})
    if "T1071" in tq:
        queries.append({"description": "Cari host dengan beaconing periodik ke IP eksternal yang sama.",
                        "filter": "category=network | pola interval tetap dst_ip", "refs": _refs_for(ctx, "T1071")})
    if "T1486" in tq:
        queries.append({"description": "Cari lonjakan modifikasi/penggantian nama berkas massal.",
                        "filter": "category=file action=rename|write | stats by host", "refs": _refs_for(ctx, "T1486")})
    if not queries:
        queries.append({"description": "Tinjau event di sekitar jendela insiden pada host terkait.",
                        "filter": f"host={ctx.host or '*'} | sort ts", "refs": _any_refs(ctx)})
    return {
        "hypothesis": (
            f"Jika {ctx.incident_code} bagian dari kampanye lebih luas, host lain mungkin "
            "menunjukkan teknik yang sama."
        ),
        "queries": queries,
        "confidence": "low",
    }


# --------------------------------------------------------------------------- #
# Ollama lokal (air-gapped)                                                   #
# --------------------------------------------------------------------------- #
class OllamaLlm:
    name = "ollama"

    def __init__(self, base_url: str, model: str, timeout: int = 30) -> None:
        assert_loopback(base_url)  # tolak egress keluar
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def generate(self, task: str, prompt: str, ctx: AgentContext) -> str:
        payload = json.dumps(
            {"model": self.model, "prompt": prompt, "stream": False, "format": "json"}
        ).encode()
        req = urllib.request.Request(
            f"{self.base_url}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # noqa: S310 (loopback-only, dijaga)
                body = json.loads(resp.read() or "{}")
        except Exception as exc:  # pragma: no cover - butuh Ollama hidup
            raise LlmError(f"panggilan LLM lokal gagal: {exc}") from exc
        return str(body.get("response", ""))


def get_llm() -> LlmClient:
    from app.core.config import get_settings

    s = get_settings()
    if s.llm_provider == "ollama":
        return OllamaLlm(s.llm_base_url, s.llm_model, s.llm_timeout_seconds)
    return StubLlm()
