# Your profile goes here

Drop your documents in this folder. Filenames are matched by keyword, so exact
names don't matter — just include the keyword in the name:

| Put in a file named like… | What it is |
|---|---|
| `resume.pdf`, `resume.docx`, `resume.txt`, `my-cv.txt` | Your resume / CV |
| `linkedin.pdf`, `linkedin.txt` | Your LinkedIn profile export |
| `profile.yaml` | *(optional)* structured overrides — see `profile.example.yaml` |

### How to export your LinkedIn profile to PDF
1. Open your LinkedIn profile.
2. Click **More** → **Save to PDF**.
3. Drop the downloaded PDF in this folder (rename it so it contains `linkedin`).

### Supported formats
`.pdf` (needs `pypdf`), `.docx` (needs `python-docx`), `.txt`, `.md`.

### Privacy
Everything in this folder is **gitignored** — your resume, LinkedIn export, and
the `jobs.db` database are never committed. The only files tracked by git are
this README and `profile.example.yaml`.
