# primordia

## ⚡ 30-Second Cold-Start Quick Reference

- **Runtime Prerequisites**: <FILL: each runtime this project needs and its minimum version>
- **Canonical Regression Shield Gate**:
  ```bash
  python aikit.py check primordia
  ```

### 🛠️ AIKit Commands (run from the AIKit folder)
| Role | Command |
|---|---|
| Status, task and gates | `python aikit.py status primordia` |
| Phase 4: every gate | `python aikit.py check primordia` |
| Repair memory and map, then check | `python aikit.py fix primordia` |
| Resume an interrupted task | `python aikit.py resume primordia` |

## 📦 What's Inside

```text
primordia/
├── .gitignore                <- transient AIKit state excluded
├── README.md
└── .aikit/                   <- this project's memory: record, ledger, decisions
```
