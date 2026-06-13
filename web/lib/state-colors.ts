// web/lib/state-colors.ts

export const STATE_COLORS = {
  STAGE_2_BULLISH: '#1A8A4E',
  HOLD:            '#5C9DCB',
  WARNING:         '#E2A53A',
  EXIT:            '#D5562C',
  BEARISH_STAGE_4: '#A21E2C',
  STAGE_1_BASING:  '#9E9E9E',
} as const

export const STATE_COLORS_LIGHT = {
  STAGE_2_BULLISH: '#2E8B57',
  HOLD:            '#3A78B4',
  WARNING:         '#C68A1E',
  EXIT:            '#B84A23',
  BEARISH_STAGE_4: '#8C1A26',
  STAGE_1_BASING:  '#888888',
} as const

export type StateKey = keyof typeof STATE_COLORS

export const STATE_SHORT: Record<StateKey, string> = {
  STAGE_2_BULLISH: 'BULLISH',
  HOLD:            'HOLD',
  WARNING:         'WARN',
  EXIT:            'EXIT',
  BEARISH_STAGE_4: 'BEAR',
  STAGE_1_BASING:  'BASE',
}

/** Returns the hex color for a state string. Falls back to gray if unknown. */
export function stateColor(state: string, light = false): string {
  const map = light ? STATE_COLORS_LIGHT : STATE_COLORS
  return map[state as StateKey] ?? (light ? '#888888' : '#666666')
}

/** Returns the compact display label for a state string. */
export function stateShortLabel(state: string): string {
  return STATE_SHORT[state as StateKey] ?? state.replaceAll('_', ' ')
}
