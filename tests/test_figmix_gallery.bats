#!/usr/bin/env bats

setup() {
  export SCRIPT="${BATS_TEST_DIRNAME}/../bin/figmix-gallery"
  export FAKE_BIN="${BATS_TEST_TMPDIR}/bin"
  export FONT_DIR="${BATS_TEST_TMPDIR}/fonts"
  export OUTPUT_DIR="${BATS_TEST_TMPDIR}/output"

  mkdir -p "${FAKE_BIN}" "${FONT_DIR}" "${OUTPUT_DIR}"
  touch "${FONT_DIR}/standard.flf" "${FONT_DIR}/ascii12.tlf"

  printf '%s\n' '#!/usr/bin/env bash' 'printf "FIGLET:%s\\n" "$*"' > "${FAKE_BIN}/figlet"
  printf '%s\n' '#!/usr/bin/env bash' 'printf "TOILET:%s\\n" "$*"' > "${FAKE_BIN}/toilet"
  printf '%s\n' '#!/usr/bin/env bash' 'output="${@: -1}"' 'printf "FAKE PNG\\n" > "${output}"' > "${FAKE_BIN}/magick"
  chmod +x "${FAKE_BIN}/figlet" "${FAKE_BIN}/toilet" "${FAKE_BIN}/magick"
}

@test "help describes the gallery options" {
  run env PATH="${FAKE_BIN}:${PATH}" "${SCRIPT}" --help

  [ "${status}" -eq 0 ]
  [[ "${output}" == *"--all-fonts"* ]]
  [[ "${output}" == *"--layout"* ]]
}

@test "text is required" {
  run env PATH="${FAKE_BIN}:${PATH}" "${SCRIPT}" --format text

  [ "${status}" -ne 0 ]
  [[ "${output}" == *"--text is required"* ]]
}

@test "generates one text and PNG variant" {
  run env PATH="${FAKE_BIN}:${PATH}" FIGMIX_FONT_DIR="${FONT_DIR}" "${SCRIPT}" \
    --text "Aaron" \
    --output-dir "${OUTPUT_DIR}" \
    --output-name "hero" \
    --engine figlet \
    --font standard \
    --layout kerning \
    --format both

  [ "${status}" -eq 0 ]
  [ -f "${OUTPUT_DIR}/hero.txt" ]
  [ -f "${OUTPUT_DIR}/hero.png" ]
  [[ "$(<"${OUTPUT_DIR}/hero.txt")" == *"FIGLET:"* ]]
  [ "$(<"${OUTPUT_DIR}/hero.png")" = "FAKE PNG" ]
}

@test "all-fonts only renders compatible fonts and records a manifest" {
  touch "${FONT_DIR}/alpha.flf" "${FONT_DIR}/beta.flf" "${FONT_DIR}/ignore.tlf"

  run env PATH="${FAKE_BIN}:${PATH}" FIGMIX_FONT_DIR="${FONT_DIR}" "${SCRIPT}" \
    --text "Aaron" \
    --output-dir "${OUTPUT_DIR}" \
    --output-name "gallery" \
    --engine figlet \
    --all-fonts \
    --format text

  [ "${status}" -eq 0 ]
  [ -f "${OUTPUT_DIR}/gallery-alpha.txt" ]
  [ -f "${OUTPUT_DIR}/gallery-beta.txt" ]
  [ -f "${OUTPUT_DIR}/gallery-manifest.md" ]
  [[ "$(<"${OUTPUT_DIR}/gallery-manifest.md")" == *"gallery-alpha.txt"* ]]
  [[ "$(<"${OUTPUT_DIR}/gallery-manifest.md")" != *"ignore"* ]]
}

@test "figlet rejects the TOIlet-only boxed layout" {
  run env PATH="${FAKE_BIN}:${PATH}" "${SCRIPT}" \
    --text "Aaron" \
    --engine figlet \
    --layout boxed

  [ "${status}" -ne 0 ]
  [[ "${output}" == *"only supported by toilet"* ]]
}

@test "TOIlet boxed layout uses its border filter" {
  run env PATH="${FAKE_BIN}:${PATH}" FIGMIX_FONT_DIR="${FONT_DIR}" "${SCRIPT}" \
    --text "Aaron" \
    --output-dir "${OUTPUT_DIR}" \
    --output-name "boxed" \
    --engine toilet \
    --font ascii12 \
    --layout boxed \
    --format text

  [ "${status}" -eq 0 ]
  [[ "$(<"${OUTPUT_DIR}/boxed.txt")" == *"TOILET:"* ]]
  [[ "$(<"${OUTPUT_DIR}/boxed.txt")" == *"-F border"* ]]
}

@test "rejects an unknown engine" {
  run env PATH="${FAKE_BIN}:${PATH}" "${SCRIPT}" \
    --text "Aaron" \
    --engine banner

  [ "${status}" -ne 0 ]
  [[ "${output}" == *"unsupported --engine 'banner'"* ]]
}
