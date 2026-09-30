import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // 사람이 읽기 힘든 함수를 새 코드부터 막는다(2026-09-30, 템플릿 a05f458). 켤 때 이미 넘던 함수 14곳은
  // 그 함수 바로 위 eslint-disable-next-line으로만 예외 — 파일 단위로 빼면 같은 파일의 새 함수가 안 걸린다.
  {
    rules: {
      complexity: ["error", 10],
      "max-lines-per-function": ["error", { max: 80, skipBlankLines: true, skipComments: true }],
    },
  },
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
]);

export default eslintConfig;
