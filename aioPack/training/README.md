# training/

Reserviert für die spätere Fine-Tuning-Stufe (nicht Teil der ersten Version).

Vorschlag für die Struktur:

```
training/
├── datasets/      # JSONL-Dateien, z. B. {"messages":[{"role":"user",...},{"role":"assistant",...}]}
├── configs/       # LoRA-/QLoRA-Konfigurationen
└── outputs/       # Adapter, Checkpoints, Evaluationsergebnisse
```

Wichtig vor dem ersten Training:

- Eigene, selbst erstellte Aufgaben und Lösungen verwenden. Kopierte W3Schools-Texte sind als
  Trainingsdaten ungeeignet (Urheberrecht/Nutzungsbedingungen).
- Lizenz des Basismodells (Llama 3.2) prüfen.
- GPU-Speicher prüfen (QLoRA für 3B-Modelle ist meist mit 8–12 GB VRAM machbar).
- Zuerst RAG stabil betreiben und eine kleine Testfragenliste anlegen, um Fine-Tuning messbar
  gegen den RAG-Stand zu vergleichen.
