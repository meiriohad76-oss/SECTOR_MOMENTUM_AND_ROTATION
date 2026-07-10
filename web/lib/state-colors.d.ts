export declare const STATE_COLORS: {
    readonly STAGE_2_BULLISH: "#1A8A4E";
    readonly HOLD: "#5C9DCB";
    readonly WARNING: "#E2A53A";
    readonly EXIT: "#D5562C";
    readonly BEARISH_STAGE_4: "#A21E2C";
    readonly STAGE_1_BASING: "#9E9E9E";
};
export declare const STATE_COLORS_LIGHT: {
    readonly STAGE_2_BULLISH: "#2E8B57";
    readonly HOLD: "#3A78B4";
    readonly WARNING: "#C68A1E";
    readonly EXIT: "#B84A23";
    readonly BEARISH_STAGE_4: "#8C1A26";
    readonly STAGE_1_BASING: "#888888";
};
export type StateKey = keyof typeof STATE_COLORS;
export declare const STATE_SHORT: Record<StateKey, string>;
/** Returns the hex color for a state string. Falls back to gray if unknown. */
export declare function stateColor(state: string, light?: boolean): string;
/** Returns the compact display label for a state string. */
export declare function stateShortLabel(state: string): string;
