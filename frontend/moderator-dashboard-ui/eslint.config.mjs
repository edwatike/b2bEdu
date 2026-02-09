import nextPlugin from "@next/eslint-plugin-next"
import reactHooks from "eslint-plugin-react-hooks"
import tseslint from "typescript-eslint"
import globals from "globals"

export default [
  {
    ignores: [".next/**", "node_modules/**", "docs/**", "dist/**"],
  },
  {
    files: ["**/*.{js,jsx,ts,tsx,mjs,cjs}"] ,
    languageOptions: {
      parser: tseslint.parser,
      ecmaVersion: "latest",
      sourceType: "module",
      globals: {
        ...globals.browser,
        ...globals.node,
      },
    },
    plugins: {
      "@next/next": nextPlugin,
      "react-hooks": reactHooks,
      "@typescript-eslint": tseslint.plugin,
    },
    rules: {
      ...(nextPlugin.configs?.["core-web-vitals"]?.rules ?? {}),
      ...(reactHooks.configs?.recommended?.rules ?? {}),
      ...(tseslint.configs?.recommended?.[0]?.rules ?? {}),

      // React Compiler / purity rules: too strict for current codebase, block lint.
      "react-hooks/purity": "off",
      "react-hooks/set-state-in-effect": "off",
      "react-hooks/immutability": "off",
      "react-hooks/incompatible-library": "off",
    },
  },
]
