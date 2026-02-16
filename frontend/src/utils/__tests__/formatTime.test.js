import { formatTime } from '../formatTime'

describe('formatTime', () => {
  test('formats zero seconds', () => {
    expect(formatTime(0)).toBe('0:00')
  })

  test('formats seconds under a minute with padding', () => {
    expect(formatTime(5)).toBe('0:05')
    expect(formatTime(9)).toBe('0:09')
  })

  test('formats exact minutes', () => {
    expect(formatTime(60)).toBe('1:00')
    expect(formatTime(120)).toBe('2:00')
  })

  test('formats minutes and seconds', () => {
    expect(formatTime(90)).toBe('1:30')
    expect(formatTime(300)).toBe('5:00')
    expect(formatTime(185)).toBe('3:05')
  })

  test('clamps negative values to zero', () => {
    expect(formatTime(-1)).toBe('0:00')
    expect(formatTime(-100)).toBe('0:00')
  })
})
