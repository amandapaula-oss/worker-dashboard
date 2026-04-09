export const theme = {
  // Texto e estrutura
  text: "#32383E",
  accent: "#FF5C35",

  // Categorias (Principal + Fundo)
  cat1: { main: "#FF5C35", bg: "#FFBEAE" },   // Laranja
  cat2: { main: "#595959", bg: "#BDBDBD" },   // Cinza
  cat3: { main: "#7869CC", bg: "#C9C3EB" },   // Roxo
  cat4: { main: "#BDE91F", bg: "#E5F8A5" },   // Verde Lima

  // Navegação
  link: "#1E7C99",
  linkVisited: "#005075",
} as const;

export const darkTheme = {
  text: "#e2e8f0",
  accent: "#FF5C35",

  cat1: { main: "#FF5C35", bg: "#5a2316" },
  cat2: { main: "#9ca3af", bg: "#374151" },
  cat3: { main: "#9b8fe8", bg: "#2e2860" },
  cat4: { main: "#c8f04c", bg: "#2e3d04" },

  link: "#38bdf8",
  linkVisited: "#7dd3fc",

  // surfaces
  pageBg:   "#0f1117",
  cardBg:   "#161b2e",
  border:   "#2a3050",
  tagBg:    "#1e2438",
  secondary:"#8892a4",
  hoverRow: "#1e2c4a",
  totalRow: "#1e2c4a",
  groupRow: "#1a2240",
} as const;

export const lightTheme = {
  text: "#32383E",
  accent: "#FF5C35",
  link: "#1E7C99",
  pageBg:    "#f4f6fb",
  cardBg:    "#ffffff",
  border:    "#dde3f0",
  tagBg:     "#f4f6fb",
  secondary: "#6b7fa3",
  hoverRow:  "#f0f4ff",
  totalRow:  "#dce6f7",
  groupRow:  "#eef2ff",
} as const;
