#!/bin/bash
# SPINE critic — автоматический аудит узлов по измеримым критериям.
# Проверяет: impulse (<=2 строк), summary (<=7 предложений по терминаторам),
# source_base (>=70% от сырья по байтам), anchors (против канона),
# vectors (#-комментарии), YAML (без голых [[ ]] в якорях).
#
# Запуск: bash tools/_critic_check.sh [nodes_dir] [raw_dir] [anchor_dump]
# Пример: bash tools/_critic_check.sh nodes raw anchors/anchor_dump.json

PROCESSED_DIR="${1:-nodes}"
RAW_DIR="${2:-raw}"
ANCHOR_DUMP="${3:-anchors/anchor_dump.json}"
FAIL_COUNT=0
PASS_COUNT=0
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

NODES="$PROCESSED_DIR"/*_*.md

echo "=== SPINE CRITIC $(date +%H:%M) ==="
echo ""

for NODE in $NODES; do
  BASENAME=$(basename "$NODE")
  NODE_ID="${BASENAME%.md}"
  FAILS=""

  # Номер чанка — последнее число в имени узла
  NUM=$(echo "$NODE_ID" | grep -oE '[0-9]+' | tail -1)
  RAW_FILE="${RAW_DIR}/U${NUM}.md"

  # 1. IMPULSE: не больше 2 строк
  IMP_LINES=$(awk '/^# IMPULSE/,/^# SUMMARY/' "$NODE" | grep -c "  " 2>/dev/null)
  if [ "$IMP_LINES" -gt 3 ]; then
    FAILS="$FAILS IMPULSE(${IMP_LINES})"
  fi

  # 2. SUMMARY: не больше 5 предложений (допуск 7)
  SUM_TEXT=$(awk '/^# SUMMARY/,/^# CLEANED/' "$NODE" 2>/dev/null)
  SUM_SENT=$(printf '%s' "$SUM_TEXT" | grep -oE '[.!?]+' | wc -l)
  if [ "$SUM_SENT" -gt 7 ]; then
    FAILS="$FAILS SUMMARY(${SUM_SENT})"
  fi

  # 3. SOURCE_BASE: не меньше 70% от сырья по байтам
  if [ -f "$RAW_FILE" ]; then
    RAW_SIZE=$(wc -c < "$RAW_FILE" 2>/dev/null)
    SRC_SIZE=$(awk '/^# SOURCE_BASE/,/^---/' "$NODE" | wc -c 2>/dev/null)
    if [ "$RAW_SIZE" -gt 0 ]; then
      SRC_PCT=$((100 * SRC_SIZE / RAW_SIZE))
      if [ "$SRC_PCT" -lt 70 ]; then
        FAILS="$FAILS SOURCE(${SRC_PCT}%<70%)"
      fi
    fi
  fi

  # 4. ANCHORS: валидация против канона
  if command -v python &>/dev/null; then
    ANC_RESULT=$(python "$SCRIPT_DIR/_check_anchors.py" "$NODE" --dump "$ANCHOR_DUMP" --quiet 2>&1)
    ANC_EXIT=$?
    if [ "$ANC_EXIT" -eq 2 ]; then
      FAILS="$FAILS ANCHORS($(printf '%s' "$ANC_RESULT" | tail -1))"
    elif [ "$ANC_EXIT" -eq 1 ]; then
      FAILS="$FAILS ANCHORS_WARN($(printf '%s' "$ANC_RESULT" | tail -1))"
    fi
  else
    ANC_COUNT=$(grep -A10 "^search_anchors:" "$NODE" | grep -c "  -" 2>/dev/null)
    if [ "$ANC_COUNT" -lt 3 ] || [ "$ANC_COUNT" -gt 5 ]; then
      FAILS="$FAILS ANCHORS(${ANC_COUNT})"
    fi
  fi

  # 5. VECTORS: каждый с # комментарием
  VEC_BLOCK=$(awk '/^vectors:/{flag=1; next} flag && /^[a-z_]+:/{flag=0} flag' "$NODE" 2>/dev/null)
  if printf '%s' "$VEC_BLOCK" | grep -q "  -.*::" 2>/dev/null; then
    VEC_NO_COMMENT=$(printf '%s' "$VEC_BLOCK" | grep "  -" | grep -v "#" | wc -l 2>/dev/null)
    if [ "$VEC_NO_COMMENT" -gt 0 ]; then
      FAILS="$FAILS VECTORS(${VEC_NO_COMMENT})"
    fi
  fi

  # 6. YAML: нет голых [[ ]] в search_anchors
  if grep -A20 "^search_anchors:" "$NODE" | grep -qE '^  - \[\[.*\]\]$' 2>/dev/null; then
    FAILS="$FAILS YAML(bare_anchors)"
  fi

  if [ -z "$FAILS" ]; then
    echo "PASS  $NODE_ID"
    PASS_COUNT=$((PASS_COUNT + 1))
  else
    echo "FAIL  $NODE_ID :$FAILS"
    FAIL_COUNT=$((FAIL_COUNT + 1))
  fi
done

echo ""
echo "=== TOTAL: $PASS_COUNT PASSED / $FAIL_COUNT FAILED ==="
[ "$FAIL_COUNT" -eq 0 ]
