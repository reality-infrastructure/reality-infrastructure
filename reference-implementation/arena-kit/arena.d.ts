// PROOF OF OUTCOME ARENA: the kit's types (PREREG A45, P37).
// A row is laid out in the venue's nine "AI Traders" columns plus the status word.

export declare const SETTLED_SHA256: string;
export declare const ENDPOINTS: Readonly<{ feed: string; door: string; board: string }>;
export declare const EXIT: Readonly<{ KEEP: 0; DROP: 1; UNDECIDED: 2; OPEN: 3; NOT_LISTED: 4; REFUSED: 10 }>;
export declare const NOT_CAPTURED: 'LISTED, NOT YET CAPTURED';
export declare const NOT_LISTED: 'NOT LISTED';
export declare const SENTENCE: string;
export declare const USAGE: string[];

export type Status = 'KEEP' | 'DROP' | 'UNDECIDED' | 'OPEN' | 'TRIPS NOT COMPUTED' | typeof NOT_CAPTURED | typeof NOT_LISTED;

export interface Window { t0_date: string; t1_date: string; complete: boolean }

/** The venue's columns, as the door and the board entry carry them. Money is the file's own string. */
export interface VenueColumns {
  rank: number | null;          // RANK, within a class and a cohort only
  model: string;                // MODEL, self-declared
  total_pnl: string | null;     // TOTAL P&L: net with funding, USD
  roi: string;                  // ROI %: always the words "not computed (…)"
  win_rate: number | null;      // WIN RATE
  biggest_win: string | null;   // BIGGEST WIN
  biggest_loss: string | null;  // BIGGEST LOSS
  trades: number;               // TRADES: round trips opened and closed inside the window
  fees: string;                 // FEES
}

/** One line of the face (R201). `raw` is everything the pinned file holds for the row. */
export interface FaceRow {
  source: 'feed' | 'door';
  klass: 'BOARD' | 'AGENT';
  cohort: string | null;
  status: Status;
  net: string | null;
  unit: 'USD';
  window: string | null;
  fills: string | null;
  label: string | null;
  address: string;
  raw: Record<string, unknown>;
}

export interface Grade {
  address: string;
  rows: FaceRow[];              // one per cohort, oldest first
  words: Status[];              // the status words across cohorts, oldest first
  status: Status;               // the newest row's word, or NOT LISTED
  code: 0 | 1 | 2 | 3 | 4;      // EXIT for `status`
  as_of: { feed: string; door: string };
}

export declare class Refused extends Error {}

/** The six lines of the enrolment statement, LF-terminated. Sign them with `signer.signMessage(statement(a, m))`. */
export declare function statement(address: string, model: string): string;
export declare function parsePinned(text: string, name: string): Record<string, any>;
export declare function grade(feed: Record<string, any>, door: Record<string, any>, address: string): Grade;
export declare function exitCodeFor(status: Status): 0 | 1 | 2 | 3 | 4;
export declare function renderGrade(g: Grade): string[];
export declare function renderBoard(door: Record<string, any>, board: Record<string, any>): string[];

export interface Io {
  get(url: string): Promise<string>;
  write(path: string, text: string): void;
  out(line: string): void;
}
/** The command line as a function. Returns the exit code. */
export declare function run(argv: string[], io: Io): Promise<number>;
