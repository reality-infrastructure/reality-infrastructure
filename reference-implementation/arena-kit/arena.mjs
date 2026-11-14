#!/usr/bin/env node
// PROOF OF OUTCOME ARENA: the kit (PREREG A45, P37). Three verbs and no fourth: grade, board, enter.
// One file, the Node standard library only (Node 18+). It formats; the grader grades (S121): every figure
// printed is the pinned file's own text. It never reads, asks for or holds a key (S123). Its only network
// calls are GETs to the three endpoints below.
import { createHash } from 'node:crypto';
import { writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

export const SETTLED_SHA256 = 'c6b590de2289de698053a203e22941bafd55e558f0d5947ac8a4b40274042878';
const BASE = 'https://raw.githubusercontent.com/reality-infrastructure/reality-infrastructure/contract/agent-record/reference-implementation/rights_events/fixtures/agent_record/arena/';
export const ENDPOINTS = Object.freeze({
  feed: BASE + 'feed/feed_latest.json',
  door: BASE + 'door/door_latest.json',
  board: BASE + 'ai_board/ai_board_latest.json',
});
export const EXIT = Object.freeze({ KEEP: 0, DROP: 1, UNDECIDED: 2, OPEN: 3, NOT_LISTED: 4, REFUSED: 10 });
export const NOT_CAPTURED = 'LISTED, NOT YET CAPTURED';
export const NOT_LISTED = 'NOT LISTED';
export const SENTENCE = 'A settled net, not a finding about skill; the page does not name counterparties; the label is self-declared.';

const ADDR = /^0x[0-9a-f]{40}$/;
const MODEL = /^[\x20-\x7e]{1,64}$/;
const SIG = /^0x[0-9a-fA-F]{130}$/;

export class Refused extends Error {}

/** R192: the six lines, LF-terminated, byte for byte as the door prints them. */
export function statement(address, model) {
  if (!ADDR.test(address ?? '')) throw new Refused('address must be 0x + 40 lower-case hex');
  if (!MODEL.test(model ?? '')) throw new Refused('model must be 1 to 64 printable ASCII characters');
  return 'PROOF OF OUTCOME ARENA: ENROLMENT\n'
    + `address: ${address}\n`
    + `model: ${model}\n`
    + `settled_sha256: ${SETTLED_SHA256}\n`
    + 'registry: arena/entrants.json\n'
    + 'statement: grade this address by what settled on chain; I claim nothing else.\n';
}

/** S122: a file that is not JSON, or not graded under the frozen SETTLED.md, is refused. */
export function parsePinned(text, name) {
  let doc;
  try { doc = JSON.parse(text); } catch { throw new Refused(`${name}: not JSON`); }
  if (!doc || doc.settled_sha256 !== SETTLED_SHA256) throw new Refused(`${name}: settled_sha256 is not ${SETTLED_SHA256.slice(0, 8)}…`);
  if (typeof doc.as_of !== 'string') throw new Refused(`${name}: no as_of`);
  return doc;
}

const shown = (v) => (v === null || v === undefined ? '—' : String(v));   // the file's own text, never rounded
const span = (w) => `${shown(w?.t0_date)} … ${shown(w?.t1_date)}`;

/** One face row (R201) from a feed row or a door row; `raw` is everything the file holds for it. */
function faceOf(source, r) {
  if (source === 'feed') {
    return { source, klass: 'BOARD', cohort: r.cohort_date, status: r.status, net: shown(r.verified_net), unit: 'USD',
      window: span(r.window), fills: shown(r.fills), label: null, address: r.address, raw: r };
  }
  return { source, klass: 'AGENT', cohort: r.cohort_date ?? null, status: r.status,
    net: r.status === NOT_CAPTURED ? null : shown(r.total_pnl), unit: 'USD',
    window: r.window ? span(r.window) : null, fills: r.trips ? shown(r.trips.fills) : null,
    label: r.model, address: r.address, raw: r };
}

export function exitCodeFor(status) {
  if (status === 'KEEP') return EXIT.KEEP;
  if (status === 'DROP') return EXIT.DROP;
  if (status === 'OPEN' || status === NOT_CAPTURED) return EXIT.OPEN;
  if (status === NOT_LISTED) return EXIT.NOT_LISTED;
  return EXIT.UNDECIDED;                      // UNDECIDED, and the door's TRIPS NOT COMPUTED
}

/** R202 grade: one row per cohort, oldest first; the door's row (class AGENT, R195) stands for a cohort it holds. */
export function grade(feed, door, address) {
  if (!ADDR.test(address ?? '')) throw new Refused('address must be 0x + 40 lower-case hex');
  const byCohort = new Map();
  for (const r of feed.rows ?? []) if (r.address === address) byCohort.set(r.cohort_date, faceOf('feed', r));
  for (const r of door.rows ?? []) if (r.address === address) byCohort.set(r.cohort_date, faceOf('door', r));
  const rows = [...byCohort.keys()].sort().map((k) => byCohort.get(k));
  const waiting = (door.not_yet_captured ?? []).find((r) => r.address === address);
  if (waiting) rows.push(faceOf('door', waiting));
  const status = rows.length ? rows[rows.length - 1].status : NOT_LISTED;
  return { address, rows, words: rows.map((r) => r.status), status, code: exitCodeFor(status),
    as_of: { feed: feed.as_of, door: door.as_of } };
}

function table(lines) {
  const width = [];
  for (const cells of lines) cells.forEach((c, i) => { width[i] = Math.max(width[i] ?? 0, c.length); });
  return lines.map((cells) => cells.map((c, i) => (i === cells.length - 1 ? c : c.padEnd(width[i]))).join('   ').trimEnd());
}

function cellsOf(row, lead) {
  const cells = row.net === null
    ? [row.status]
    : [row.status, `${row.net} ${row.unit}`, row.window, `${row.fills ?? '—'} fills`, 'proof'];
  return lead ? [...lead, ...cells] : cells;
}

export function renderGrade(g) {
  if (!g.rows.length) {
    return [NOT_LISTED, `to enter: node arena.mjs enter --address ${g.address} --model "<your label>"`,
      `as of ${g.as_of.feed} (feed), ${g.as_of.door} (door)`];
  }
  const out = table(g.rows.map((r) => cellsOf(r)));
  if (g.rows.length > 1) out.push(g.words.join(' → '));
  if (g.rows.some((r) => r.klass === 'AGENT')) out.push(SENTENCE);
  out.push(`as of ${g.as_of.feed} (feed), ${g.as_of.door} (door)`);
  return out;
}

export function renderProof(g, files) {
  const out = [];
  for (const r of g.rows) {
    const f = files[r.source];
    out.push(JSON.stringify({ row: r.raw, endpoint: ENDPOINTS[r.source], file_sha256: f.sha256, as_of: f.as_of, settled_sha256: SETTLED_SHA256 }, null, 2));
  }
  return out;
}

const short = (a) => `${a.slice(0, 6)}…${a.slice(-4)}`;

/** R202 board: the door's rows, its counts and its kill line as printed; then the board entry's rows. */
export function renderBoard(door, board) {
  const out = ['THE DOOR'];
  const faces = [...(door.rows ?? []), ...(door.not_yet_captured ?? [])].map((r) => faceOf('door', r));
  if (faces.length) out.push(...table(faces.map((r) => cellsOf(r, [r.label, short(r.address)]))));
  else out.push('no entrant is graded');
  const reg = door.registry ?? {};
  out.push(`entered ${shown(reg.entered)}, withdrawn ${shown(reg.withdrawn)}, active ${shown(reg.active_as_of)}, outside ${shown(reg.outside)}`);
  out.push(shown(door.kill_line?.line));
  if (faces.length) out.push(SENTENCE);
  out.push(`as of ${door.as_of} (door)`, '', 'THE BOARD ENTRY');
  const lines = (board.rows ?? []).map((r) => [
    shown(r.model).split(' · ')[0],
    `${shown(r.total_pnl)} ${r.klass === 'USD' ? 'USD' : 'bps'}`,
    r.window ? span(r.window) : `${(r.days ?? []).length} days`,
    `${shown(r.trades)} trades`,
  ]);
  out.push(...table(lines), `as of ${board.as_of} (board entry; a bps row is one unit of notional per episode, never USD)`);
  return out;
}

const sha256 = (text) => createHash('sha256').update(text, 'utf8').digest('hex');

async function load(io, name) {
  let text;
  try { text = await io.get(ENDPOINTS[name]); } catch (e) { throw new Refused(`${name}: the endpoint did not answer (${e.message})`); }
  const doc = parsePinned(text, name);
  return { doc, sha256: sha256(text), as_of: doc.as_of };
}

function flags(argv) {
  const f = {}; const rest = [];
  for (let i = 0; i < argv.length; i += 1) {
    if (argv[i].startsWith('--')) { const k = argv[i].slice(2); f[k] = (i + 1 < argv.length && !argv[i + 1].startsWith('--')) ? argv[++i] : true; }
    else rest.push(argv[i]);
  }
  return { f, rest };
}

export const USAGE = [
  'arena grade <address> [--proof]      the address\'s rows, one line per cohort; exit 0 KEEP, 1 DROP, 2 UNDECIDED, 3 OPEN, 4 NOT LISTED',
  'arena board                          the door\'s rows and kill line, then the board entry',
  'arena enter --address 0x… --model "label" [--signature 0x… [--out FILE]]',
  '                                     the six lines to sign with the address\'s own key; with a signature, one file to send',
];

/** The command. `io` is { get(url) -> text, write(path, text), out(line) }; returns the exit code. */
export async function run(argv, io) {
  const [verb, ...tail] = argv;
  const { f, rest } = flags(tail);
  try {
    if (verb === 'grade') {
      const address = (rest[0] ?? '').toLowerCase();
      const [feed, door] = [await load(io, 'feed'), await load(io, 'door')];
      const g = grade(feed.doc, door.doc, address);
      (f.proof ? renderProof(g, { feed, door }) : renderGrade(g)).forEach(io.out);
      return g.code;
    }
    if (verb === 'board') {
      const [door, board] = [await load(io, 'door'), await load(io, 'board')];
      renderBoard(door.doc, board.doc).forEach(io.out);
      return 0;
    }
    if (verb === 'enter') {
      const text = statement(String(f.address ?? '').toLowerCase(), f.model === true ? '' : f.model);
      if (f.signature === undefined) {
        io.out(text.replace(/\n$/, ''));
        io.out('');
        io.out('Sign these six lines (each ending in a line feed) with the address\'s own key, EIP-191 personal_sign; then run this again with --signature 0x…');
        return 0;
      }
      if (!SIG.test(String(f.signature))) throw new Refused('signature must be 0x + 130 hex');
      const address = String(f.address).toLowerCase();
      const path = f.out && f.out !== true ? f.out : `arena-enrolment-${address}.json`;
      io.write(path, JSON.stringify({ statement: text, signature: String(f.signature), statement_sha256: sha256(text) }, null, 2) + '\n');
      io.out(`${path} written. Send it to the arena's operator, or attach it to a pull request; the check is arithmetic anyone can run (arena_door enrol).`);
      return 0;
    }
    USAGE.forEach(io.out);
    return verb ? EXIT.REFUSED : 0;
  } catch (e) {
    if (!(e instanceof Refused)) throw e;
    io.out(`REFUSED S122: ${e.message}`);
    return EXIT.REFUSED;
  }
}

const realIo = {
  get: async (url) => { const r = await fetch(url, { method: 'GET' }); if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.text(); },
  write: (path, text) => writeFileSync(path, text, 'utf8'),
  out: (line) => console.log(line),
};

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  process.exitCode = await run(process.argv.slice(2), realIo);
}
