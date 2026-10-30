import { describe, it, expect } from 'vitest';
import {
  formatPct,
  formatMinutes,
  formatSimulatedDate,
  formatServerTimestamp,
  formatLOS,
  formatCount,
} from '@/lib/format';

describe('format utilities', () => {
  describe('formatPct', () => {
    it('formats decimals to percentages (rounded by default)', () => {
      expect(formatPct(0.854)).toBe('85%');
      expect(formatPct(1.0)).toBe('100%');
      expect(formatPct(0)).toBe('0%');
    });

    it('handles custom decimal precision', () => {
      expect(formatPct(0.8542, 2)).toBe('85.42%');
      expect(formatPct(0.8542, 1)).toBe('85.4%');
      expect(formatPct(0.8542, 0)).toBe('85%');
    });

    it('handles undefined or null gracefully', () => {
      expect(formatPct(undefined)).toBe('—');
      expect(formatPct(null)).toBe('—');
      expect(formatPct(NaN)).toBe('—');
    });
  });

  describe('formatMinutes', () => {
    it('formats minute durations clearly', () => {
      expect(formatMinutes(45)).toBe('45m');
      expect(formatMinutes(90)).toBe('1h 30m');
      expect(formatMinutes(120)).toBe('2h');
      expect(formatMinutes(0)).toBe('0m');
    });

    it('handles undefined/null durations', () => {
      expect(formatMinutes(undefined)).toBe('—');
      expect(formatMinutes(null)).toBe('—');
    });
  });

  describe('formatSimulatedDate', () => {
    it('formats ISO simulated timestamps without computing relative time to current clock', () => {
      const formatted = formatSimulatedDate('2026-03-14T08:30:00');
      expect(formatted).toContain('Mar');
      expect(formatted).toContain('08:30');
    });

    it('returns fallback for invalid string or null', () => {
      expect(formatSimulatedDate(undefined)).toBe('—');
      expect(formatSimulatedDate('')).toBe('—');
      expect(formatSimulatedDate('not-a-date')).toBe('—');
    });
  });

  describe('formatServerTimestamp', () => {
    it('formats server UTC timestamp string with UTC designation', () => {
      const formatted = formatServerTimestamp('2026-10-30T17:15:00Z');
      expect(formatted).toContain('UTC');
    });

    it('returns placeholder for empty input or invalid string', () => {
      expect(formatServerTimestamp(undefined)).toBe('—');
      expect(formatServerTimestamp('')).toBe('—');
      expect(formatServerTimestamp('invalid')).toBe('—');
    });
  });

  describe('formatLOS', () => {
    it('formats predicted length of stay in days', () => {
      expect(formatLOS(3.5)).toBe('3.5d');
      expect(formatLOS(1.0)).toBe('1.0d');
    });

    it('handles undefined input', () => {
      expect(formatLOS(undefined)).toBe('—');
      expect(formatLOS(null)).toBe('—');
    });
  });

  describe('formatCount', () => {
    it('formats large numbers with commas', () => {
      expect(formatCount(1200)).toBe('1,200');
      expect(formatCount(45)).toBe('45');
    });

    it('handles undefined or null', () => {
      expect(formatCount(undefined)).toBe('—');
      expect(formatCount(null)).toBe('—');
    });
  });
});
