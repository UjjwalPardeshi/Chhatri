import { describe, expect, it } from 'vitest'

import { ageLabel, clipDuration, dayLabel, durationLabel, hhmm, hhmmAfter, minutesBetween, slaState, weekdayDayLabel } from './time'

const AT = '2025-08-19T17:04:00+05:30'

describe('time helpers (IST wall clock, simulated spans)', () => {
  it('reads HH:MM as written', () => {
    expect(hhmm(AT)).toBe('17:04')
    expect(hhmm(null)).toBe('—')
    expect(hhmm('nonsense')).toBe('—')
    expect(hhmmAfter('2025-08-21T11:25:00+05:30', 4)).toBe('11:29')
    expect(hhmmAfter('2025-08-19T23:58:00+05:30', 5)).toBe('00:03')
    expect(hhmmAfter(null, 4)).toBe('—')
    expect(hhmmAfter('nonsense', 4)).toBe('—')
  })

  it('labels days', () => {
    expect(dayLabel(AT)).toBe('19 Aug 2025')
    expect(dayLabel('2025-08-25')).toBe('25 Aug 2025')
    expect(dayLabel(undefined)).toBe('—')
    expect(weekdayDayLabel(AT)).toBe('Tue 19 Aug')
    expect(weekdayDayLabel('2025-08-18')).toBe('Mon 18 Aug')
    expect(weekdayDayLabel(null)).toBe('—')
  })

  it('measures minutes between instants', () => {
    expect(minutesBetween('2025-08-19T17:00:00+05:30', AT)).toBe(4)
    expect(minutesBetween(AT, '2025-08-19T17:00:00+05:30')).toBe(-4)
    expect(minutesBetween('x', AT)).toBeNull()
  })

  it('formats durations', () => {
    expect(durationLabel(40)).toBe('40 min')
    expect(durationLabel(120)).toBe('2 h')
    expect(durationLabel(95)).toBe('1 h 35 min')
    expect(durationLabel(-95)).toBe('1 h 35 min')
  })

  it('counts SLA down on simulated time', () => {
    const due = '2025-08-20T17:05:00+05:30'
    expect(slaState(due, '2025-08-19T17:05:00+05:30')).toEqual({ label: '24 h left', tone: 'ok' })
    expect(slaState(due, '2025-08-20T14:05:00+05:30')).toEqual({ label: '3 h left', tone: 'warn' })
    expect(slaState(due, '2025-08-20T18:00:00+05:30')).toEqual({ label: 'overdue 55 min', tone: 'overdue' })
    expect(slaState(due, 'bad').label).toBe('—')
  })

  it('shows ages and clip durations', () => {
    expect(ageLabel(AT, AT)).toBe('just now')
    expect(ageLabel('2025-08-19T17:00:00+05:30', AT)).toBe('4 min ago')
    expect(ageLabel('bad', AT)).toBe('—')
    expect(clipDuration(4)).toBe('0:04')
    expect(clipDuration(66)).toBe('1:06')
    expect(clipDuration(-3)).toBe('0:00')
  })
})
