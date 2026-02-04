module.exports = {
  root: true,
  env: {
    browser: true,
    es2020: true,
    node: true,
  },
  parser: "@typescript-eslint/parser",
  plugins: ["react-hooks", "react-refresh"],
  extends: [
    "eslint:recommended",
    "plugin:react-hooks/recommended",
  ],
  settings: {
    react: {
      version: "detect",
    },
  },
  ignorePatterns: [
    "dist",
    "node_modules",
    "src/pages/QueryPage_backup.tsx",
    "**/*backup*.ts",
    "**/*backup*.tsx",
  ],
  rules: {
    // Keep the gate lightweight for now: prevent hard failures from existing legacy patterns.
    "no-undef": "off",
    "no-unused-vars": "off",
    "no-useless-escape": "off",
    "no-extra-semi": "off",
    "prefer-const": "off",
    "react-hooks/exhaustive-deps": "off",
    "react-refresh/only-export-components": "off",
  },
};
