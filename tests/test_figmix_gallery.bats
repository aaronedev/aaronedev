#!/usr/bin/env bats

setup() {
  export SCRIPT="${BATS_TEST_DIRNAME}/../bin/figmix-gallery"
  export FAKE_BIN="${BATS_TEST_TMPDIR}/bin"
  export OUTPUT_DIR="${BATS_TEST_TMPDIR}/output"
  export SOURCE_MODULE="${BATS_TEST_TMPDIR}/toiletbox_figletbox.sh"
  export ANSILOVE_LOG="${BATS_TEST_TMPDIR}/ansilove.log"
  export SOURCE_MARKER="${BATS_TEST_TMPDIR}/source-marker"

  mkdir -p "${FAKE_BIN}" "${OUTPUT_DIR}"

  printf '%s\n' \
    '#!/usr/bin/env bash' \
    'output=""' \
    'arguments="$*"' \
    'while (($# > 0)); do' \
    '  case "$1" in -o) output="$2"; shift 2 ;; *) input="$1"; shift ;; esac' \
    'done' \
    'printf "ansilove %s\\n" "${arguments}" >> "${ANSILOVE_LOG}"' \
    'printf "FAKE PNG from %s\\n" "${input}" > "${output}"' > "${FAKE_BIN}/ansilove"
  chmod +x "${FAKE_BIN}/ansilove"

  printf '%s\n' \
    '__banner_toilet_fonts=(toilet-one toilet-two)' \
    '__banner_figlet_fonts=(figlet-one figlet-two)' \
    '__banner_boxes=(box-one box-two)' \
    '__banner_toilet_filters=(rainbow metal)' \
    '[[ -z ${SOURCE_MARKER:-} ]] || printf sourced > "${SOURCE_MARKER}"' \
    '__banner_default_font() {' \
    '  case "$1/$2" in' \
    "    figlet/head) printf '%s\\n' 'ANSI Shadow' ;;" \
    "    figlet/tail) printf '%s\\n' small ;;" \
    "    toilet/head) printf '%s\\n' bigmono12 ;;" \
    "    toilet/tail) printf '%s\\n' smblock ;;" \
    '  esac' \
    '}' \
    'record_argv() {' \
    '  local name=$1' \
    '  shift' \
    '  printf "%s:" "$name"' \
    '  printf " <%s>" "$@"' \
    '  printf "\\n"' \
    '}' \
    'figmix() { record_argv FIGMIX "$@"; }' \
    'toiletbox() { record_argv TOILETBOX "$@"; }' \
    'figletbox() { record_argv FIGLETBOX "$@"; }' > "${SOURCE_MODULE}"
}

@test "help describes source-backed capture and exhaustive mix modes" {
  run "${SCRIPT}" --help

  [ "${status}" -eq 0 ]
  [[ "${output}" == *"--capture"* ]]
  [[ "${output}" == *"--all-mixes"* ]]
  [[ "${output}" == *"require an explicit --output-dir"* ]]
  [[ "${output}" == *"FIGMIX_BASH_SOURCE"* ]]
}

@test "fails clearly when the canonical source module is unavailable" {
  run env FIGMIX_BASH_SOURCE="${BATS_TEST_TMPDIR}/missing.sh" "${SCRIPT}" \
    --profile --text "Aaron"

  [ "${status}" -ne 0 ]
  [[ "${output}" == *"canonical source module was not found"* ]]
}

@test "profile uses the exact figmix word-split composition and ansilove" {
  run env PATH="${FAKE_BIN}:${PATH}" FIGMIX_BASH_SOURCE="${SOURCE_MODULE}" "${SCRIPT}" \
    --profile \
    --text "Aaron Dev" \
    --output-dir "${OUTPUT_DIR}" \
    --format both

  [ "${status}" -eq 0 ]
  [ -f "${OUTPUT_DIR}/profile-hero.txt" ]
  [ -f "${OUTPUT_DIR}/profile-hero.png" ]
  [[ "$(<"${OUTPUT_DIR}/profile-hero.txt")" == "FIGMIX: <--word> <-H> <slant> <-T> <small> <Aaron Dev>" ]]
  [[ "$(<"${ANSILOVE_LOG}")" == *"-o ${OUTPUT_DIR}/profile-hero.png"* ]]
}

@test "capture forwards a mixed figmix style verbatim and appends text only once" {
  run env PATH="${FAKE_BIN}:${PATH}" FIGMIX_BASH_SOURCE="${SOURCE_MODULE}" "${SCRIPT}" \
    --capture figmix \
    --text "AARON DEV" \
    --output-name mixed \
    --output-dir "${OUTPUT_DIR}" \
    --format text \
    -- --head-engine toilet --tail-engine figlet -H future -T slant \
      --head-filter metal --word --space 5 --align bottom --box ansi-rounded

  [ "${status}" -eq 0 ]
  [[ "$(<"${OUTPUT_DIR}/mixed.txt")" == \
    "FIGMIX: <--head-engine> <toilet> <--tail-engine> <figlet> <-H> <future> <-T> <slant> <--head-filter> <metal> <--word> <--space> <5> <--align> <bottom> <--box> <ansi-rounded> <AARON DEV>" ]]
  [[ "$(<"${OUTPUT_DIR}/figmix-gallery-manifest.md")" == *"--head-engine toilet"* ]]
}

@test "capture with explicit figmix head and tail does not append text" {
  run env PATH="${FAKE_BIN}:${PATH}" FIGMIX_BASH_SOURCE="${SOURCE_MODULE}" "${SCRIPT}" \
    --capture figmix \
    --output-name explicit \
    --output-dir "${OUTPUT_DIR}" \
    --format text \
    -- --head AARON --tail DEV --head-engine figlet --tail-engine toilet

  [ "${status}" -eq 0 ]
  [[ "$(<"${OUTPUT_DIR}/explicit.txt")" == \
    "FIGMIX: <--head> <AARON> <--tail> <DEV> <--head-engine> <figlet> <--tail-engine> <toilet>" ]]
}

@test "capture forwards toiletbox box and filter arguments verbatim" {
  run env PATH="${FAKE_BIN}:${PATH}" FIGMIX_BASH_SOURCE="${SOURCE_MODULE}" "${SCRIPT}" \
    --capture toiletbox \
    --text "AARON DEV" \
    --output-name toilet \
    --output-dir "${OUTPUT_DIR}" \
    --format text \
    -- -f future -F rainbow --box ansi-heavy

  [ "${status}" -eq 0 ]
  [[ "$(<"${OUTPUT_DIR}/toilet.txt")" == \
    "TOILETBOX: <-f> <future> <-F> <rainbow> <--box> <ansi-heavy> <AARON DEV>" ]]
}

@test "capture rejects live timer options because they cannot yield a stable asset" {
  run env PATH="${FAKE_BIN}:${PATH}" FIGMIX_BASH_SOURCE="${SOURCE_MODULE}" "${SCRIPT}" \
    --capture figmix --text "Aaron" --output-name timer --format text -- --timer 5s

  [ "${status}" -ne 0 ]
  [[ "${output}" == *"timer options cannot be captured as static assets"* ]]
}

@test "all refuses an implicit output path before sourcing the banner module" {
  cd "${BATS_TEST_TMPDIR}"

  run env PATH="${FAKE_BIN}:${PATH}" FIGMIX_BASH_SOURCE="${SOURCE_MODULE}" \
    SOURCE_MARKER="${SOURCE_MARKER}" "${SCRIPT}" --all --text "Aaron Dev" --format text

  [ "${status}" -ne 0 ]
  [[ "${output}" == *"--output-dir is required for --all"* ]]
  [ ! -e "${SOURCE_MARKER}" ]
}

@test "all-mixes refuses an implicit output path before sourcing the banner module" {
  cd "${BATS_TEST_TMPDIR}"

  run env PATH="${FAKE_BIN}:${PATH}" FIGMIX_BASH_SOURCE="${SOURCE_MODULE}" \
    SOURCE_MARKER="${SOURCE_MARKER}" "${SCRIPT}" --all-mixes --text "Aaron Dev" --format text

  [ "${status}" -ne 0 ]
  [[ "${output}" == *"--output-dir is required for --all-mixes"* ]]
  [ ! -e "${SOURCE_MARKER}" ]
}

@test "all includes source fonts boxes filters and all four figmix engine pairings" {
  run env PATH="${FAKE_BIN}:${PATH}" FIGMIX_BASH_SOURCE="${SOURCE_MODULE}" "${SCRIPT}" \
    --all \
    --text "Aaron Dev" \
    --output-dir "${OUTPUT_DIR}" \
    --format text

  [ "${status}" -eq 0 ]
  [ -f "${OUTPUT_DIR}/toiletbox-font-toilet-one.txt" ]
  [ -f "${OUTPUT_DIR}/toiletbox-box-box-two.txt" ]
  [ -f "${OUTPUT_DIR}/toiletbox-filter-metal.txt" ]
  [ -f "${OUTPUT_DIR}/figletbox-font-figlet-two.txt" ]
  [ -f "${OUTPUT_DIR}/figletbox-box-box-two.txt" ]
  [ -f "${OUTPUT_DIR}/figmix-engine-toilet-figlet.txt" ]
  [[ "$(<"${OUTPUT_DIR}/toiletbox-filter-metal.txt")" == "TOILETBOX: <-F> <metal> <Aaron Dev>" ]]
  [[ "$(<"${OUTPUT_DIR}/figmix-engine-toilet-figlet.txt")" == \
    "FIGMIX: <--head-engine> <toilet> <--tail-engine> <figlet> <-H> <bigmono12> <-T> <small> <--word> <Aaron Dev>" ]]
  [[ "$(<"${OUTPUT_DIR}/figmix-gallery-manifest.md")" == *"figletbox -b box-two"* ]]
}

@test "all-mixes records every ordered source font pair across four real engine combinations" {
  run env PATH="${FAKE_BIN}:${PATH}" FIGMIX_BASH_SOURCE="${SOURCE_MODULE}" "${SCRIPT}" \
    --all-mixes \
    --text "Aaron Dev" \
    --output-dir "${OUTPUT_DIR}" \
    --format text

  [ "${status}" -eq 0 ]
  [ "$(find "${OUTPUT_DIR}" -name 'figmix-mix-*.txt' | wc -l | tr -d ' ')" -eq 16 ]
  [ -f "${OUTPUT_DIR}/figmix-mix-figlet-figlet-figlet-one-figlet-two.txt" ]
  [ -f "${OUTPUT_DIR}/figmix-mix-figlet-toilet-figlet-two-toilet-one.txt" ]
  [ -f "${OUTPUT_DIR}/figmix-mix-toilet-figlet-toilet-two-figlet-one.txt" ]
  [ -f "${OUTPUT_DIR}/figmix-mix-toilet-toilet-toilet-two-toilet-one.txt" ]
  [[ "$(<"${OUTPUT_DIR}/figmix-mix-toilet-figlet-toilet-two-figlet-one.txt")" == \
    "FIGMIX: <--head-engine> <toilet> <--tail-engine> <figlet> <-H> <toilet-two> <-T> <figlet-one> <--word> <Aaron Dev>" ]]
}
