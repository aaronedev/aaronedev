#!/usr/bin/env bats

setup() {
  export SCRIPT="${BATS_TEST_DIRNAME}/../bin/figmix-gallery"
  export FAKE_BIN="${BATS_TEST_TMPDIR}/bin"
  export OUTPUT_DIR="${BATS_TEST_TMPDIR}/output"
  export SOURCE_MODULE="${BATS_TEST_TMPDIR}/toiletbox_figletbox.sh"
  export ANSILOVE_LOG="${BATS_TEST_TMPDIR}/ansilove.log"

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
    'figmix() { printf "FIGMIX:%s\\n" "$*"; }' \
    'toiletbox() { printf "TOILETBOX:%s\\n" "$*"; }' \
    'figletbox() { printf "FIGLETBOX:%s\\n" "$*"; }' > "${SOURCE_MODULE}"
}

@test "help describes the dotfile-backed collection modes" {
  run "${SCRIPT}" --help

  [ "${status}" -eq 0 ]
  [[ "${output}" == *"--profile"* ]]
  [[ "${output}" == *"--all"* ]]
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
  [[ "$(<"${OUTPUT_DIR}/profile-hero.txt")" == "FIGMIX:--word -H slant -T small Aaron Dev" ]]
  [[ "$(<"${ANSILOVE_LOG}")" == *"-o ${OUTPUT_DIR}/profile-hero.png"* ]]
}

@test "all uses source arrays and functions and records the exact commands" {
  run env PATH="${FAKE_BIN}:${PATH}" FIGMIX_BASH_SOURCE="${SOURCE_MODULE}" "${SCRIPT}" \
    --all \
    --text "Aaron Dev" \
    --output-dir "${OUTPUT_DIR}" \
    --format both

  [ "${status}" -eq 0 ]
  [ -f "${OUTPUT_DIR}/figmix-auto.txt" ]
  [ -f "${OUTPUT_DIR}/figmix-word-split.txt" ]
  [ -f "${OUTPUT_DIR}/figmix-toilet.txt" ]
  [ -f "${OUTPUT_DIR}/toiletbox-font-toilet-one.txt" ]
  [ -f "${OUTPUT_DIR}/toiletbox-box-box-two.txt" ]
  [ -f "${OUTPUT_DIR}/figletbox-font-figlet-two.txt" ]
  [ -f "${OUTPUT_DIR}/figmix-gallery-manifest.md" ]
  [[ "$(<"${OUTPUT_DIR}/figmix-auto.txt")" == "FIGMIX:--auto Aaron Dev" ]]
  [[ "$(<"${OUTPUT_DIR}/figmix-toilet.txt")" == "FIGMIX:--toilet -H bigmono12 -T smblock Aaron Dev" ]]
  [[ "$(<"${OUTPUT_DIR}/toiletbox-font-toilet-one.txt")" == "TOILETBOX:-f toilet-one Aaron Dev" ]]
  [[ "$(<"${OUTPUT_DIR}/toiletbox-box-box-two.txt")" == "TOILETBOX:-b box-two Aaron Dev" ]]
  [[ "$(<"${OUTPUT_DIR}/figletbox-font-figlet-two.txt")" == "FIGLETBOX:-f figlet-two Aaron Dev" ]]
  [[ "$(<"${OUTPUT_DIR}/figmix-gallery-manifest.md")" == *"figmix --word -H slant -T small"* ]]
  [[ "$(<"${OUTPUT_DIR}/figmix-gallery-manifest.md")" == *"toiletbox -f toilet-one"* ]]
  [[ "$(<"${OUTPUT_DIR}/figmix-gallery-manifest.md")" == *"figletbox -f figlet-two"* ]]
  [ -f "${OUTPUT_DIR}/figmix-toilet.png" ]
  [[ "$(<"${ANSILOVE_LOG}")" == *"figmix-toilet.png"* ]]
}
