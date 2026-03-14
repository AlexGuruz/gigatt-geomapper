path = "plan.md"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

needle = "| 7.2 | Expose in Geomapper"
insertion = '''

**Phase 7 acceptance criteria**

- [ ] Jobs/opportunity routes filterable by distance from driver's projected_available_location (e.g. 150-300 mi).
- [ ] "Routes near Driver X's next free location" exposed in Geomapper.

'''

if "**Phase 7 acceptance criteria**" in content:
    print("Already has Phase 7 acceptance criteria")
else:
    idx = content.find(needle)
    if idx < 0:
        print("Needle not found")
    else:
        # Find end of line (after the | ☐ |)
        end = content.find("\n\n---", idx)
        if end < 0:
            end = content.find("\n", idx + 200)
        content = content[:end] + insertion + content[end:]
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print("Done")
