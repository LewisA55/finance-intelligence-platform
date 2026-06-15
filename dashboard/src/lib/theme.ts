// Centralised chart palette for the light institutional management-pack design.
// Colour discipline:
//   - charcoal/black = primary data series (the brand anchor)
//   - muted steel    = secondary series
//   - green          = favourable variance ONLY
//   - red/burgundy   = adverse variance ONLY
//   - amber          = control warnings ONLY
export const chart = {
  primary: '#1a1a1a', // charcoal/black — primary anchor series
  secondary: '#6b7c93', // muted steel — secondary series
  favourable: '#2e7d5b', // restrained green — favourable only
  adverse: '#9b2c3a', // burgundy — adverse only
  amber: '#b07a1e', // control warning only
  budget: '#b8b5ad', // grey — plan / budget reference line
  grid: '#ece9e2', // very light gridlines
  axis: '#8a8a85', // muted axis labels
} as const;
