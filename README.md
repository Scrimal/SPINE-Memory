# SPINE-Memory

Методология структурирования долговременной памяти агента в виде направленного
графа. Репозиторий содержит спецификацию (`methodology/`), рабочий демо-пример
(обработка бортового журнала экспедиции «Кедр-9» из трёх сырых чанков в три
полноценные spine-ноды) и набор инструментов валидации (`tools/`).

## Структура

```
.
├── methodology/
│   └── SPINE_METHODOLOGY.md   # спецификация формата и правил
├── raw/
│   ├── U001.md                # сырой чанк №1
│   ├── U002.md                # сырой чанк №2
│   └── U003.md                # сырой чанк №3
├── nodes/
│   ├── KEDR_001.md            # обработанный узел (домен «Связь»)
│   ├── KEDR_002.md            # обработанный узел (домен «Карта»)
│   └── KEDR_003.md            # обработанный узел (домен «Тайны_Груза»)
├── anchors/
│   └── anchor_dump.json       # канон якорей демо-графа
└── tools/                     # утилиты валидации и обхода
    ├── _critic_check.sh
    ├── _check_anchors.py
    ├── _crosslink.py
    ├── _wander.py
    └── _quality_audit.py
```

## Быстрый старт

Все команды запускаются из корня репозитория.

```bash
# 1. Автоаудит нод (PASS без предупреждений)
bash tools/_critic_check.sh nodes raw

# 2. Валидация якорей против канона
python tools/_check_anchors.py nodes/KEDR_001.md --dump anchors/anchor_dump.json --quiet

# 3. Обход графа (прямые и обратные связи)
python tools/_wander.py --from KEDR_001 --hops 2 --folder nodes

# 4. Глобальный аудит качества
python tools/_quality_audit.py --nodes nodes --raw raw
```

## Формат узла (v2.1)

```
---                          # YAML-фронтматтер
id: KEDR_001
type: spine_node
domain: Связь
hub: "[[Кедр_Связь]]"
constellation: Экспедиция Кедр-9
vectors:
  - "связь::трёхслойный_архив"  # комментарий
search_anchors:
  - трёхслойный_архив
chronology:
  roots: "[[U001]]"
  after: "[[KEDR_002]]:continuation"
semantic_links:
  - "[[KEDR_002]]::продолжение"
---

# IMPULSE        — 1–2 строки
# SUMMARY        — 3–5 предложений
# CLEANED_DATA   — ~25 строк фактов
# IMPACT         — strategic_weight + key_insight
# SOURCE_BASE    — ≥70% исходного текста
---
```

Полная спецификация — в `methodology/SPINE_METHODOLOGY.md`.
