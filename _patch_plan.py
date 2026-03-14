# Add Phase 0, 5, 7 acceptance criteria to plan.md
path = "plan.md"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Phase 0
old0 = "**Why:** If implementation starts without this baseline, "preserve existing behavior" is ambiguous and the current app can be damaged by well-meaning edits.\n\n### Phase 1 "
new0 = """**Why:** If implementation starts without this baseline, "preserve existing behavior" is ambiguous and the current app can be damaged by well-meaning edits.

**Phase 0 acceptance criteria**

- [ ] All endpoints, map behaviors, left sidebar behaviors documented.
- [ ] Regression checklist created.
- [ ] routes.json / drivers.json schema and read paths documented.
- [ ] Focus behavior in app.js documented.

### Phase 1 """

# Phase 5
old5 = "| 5.6 | Right sidebar "Unassigned jobs" (or "Incoming permits") panel: job cards with Assign driver. Assign driver flow: select job → show drivers → assign → job and driver update; driver card and map update (reuse Phase 3). | ☐ |\n\n### Phase 6 "
new5 = """| 5.6 | Right sidebar "Unassigned jobs" (or "Incoming permits") panel: job cards with Assign driver. Assign driver flow: select job → show drivers → assign → job and driver update; driver card and map update (reuse Phase 3). | ☐ |

**Phase 5 acceptance criteria**

- [ ] Ingestion intake and parse work (PDF and at least one image type).
- [ ] Review UI shows extracted fields; approve/reject; no job without review.
- [ ] create-job from approved candidate; job appears in unassigned list.
- [ ] Unassigned jobs panel; assign driver flow updates job and driver.

### Phase 6 """

# Phase 7
old7 = "| 7.2 | Expose in Geomapper (e.g. \"Routes near Driver X's next free location\"). | ☐ |\n\n---\n\n## 12. Driver Experience"
new7 = """| 7.2 | Expose in Geomapper (e.g. "Routes near Driver X's next free location"). | ☐ |

**Phase 7 acceptance criteria**

- [ ] Jobs filtered by distance from driver projected_available_location.
- [ ] "Routes near Driver X" (or equivalent) exposed in Geomapper.

---

## 12. Driver Experience"""

for old, new in [(old0, new0), (old5, new5), (old7, new7)]:
    if old in content:
        content = content.replace(old, new, 1)
        print("Replaced successfully")
    else:
        print("NOT FOUND:", repr(old[:80]))

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("Done")
