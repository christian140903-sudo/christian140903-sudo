# ts-compute

Verteilte Rechenläufe für ein offenes Technosignatur-Forschungsprojekt
(Neuanalyse öffentlicher astronomischer Archivdaten). Dieser Ordner lebt nur auf
dem Branch `claude/technosignatures-archive-analysis-nxoino`; `main` bleibt
unberührt.

- Auftrag: `jobs/current.json` (`job`, `nshards`, `args`). Ein Push dieser Datei
  startet den Workflow `.github/workflows/ts-compute.yml`.
- Jeder Shard führt `python -m tsjobs.run` aus und schreibt CSV + Meta-JSON.
- `gather` hängt die Shards zusammen und legt sie auf Branch `ts-results` unter
  `runs/<run_id>/` ab.
- Ergebnisse sind Rohdaten für weitere Prüfung, keine Befunde.
