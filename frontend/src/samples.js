// Sample networks.

// Uniform four-tensor ring: all 10 realizable trees tie — the smoke network.
export const RING4_SAMPLE = {
  tensors: [
    { name: 'A', indexText: 'i j' },
    { name: 'B', indexText: 'j k' },
    { name: 'C', indexText: 'k l' },
    { name: 'D', indexText: 'l i' },
  ],
  dims: ['i', 'j', 'k', 'l'].map((name) => ({ name, dim: '2' })),
}

// Star with a fat center: locally-cheapest pair choices build a giant
// intermediate; peak-first optimization avoids it.
export const STAR_SAMPLE = {
  tensors: [
    { name: 'C', indexText: 'a b c d' },
    { name: 'A', indexText: 'a' },
    { name: 'B', indexText: 'b' },
    { name: 'D', indexText: 'c' },
    { name: 'E', indexText: 'd' },
  ],
  dims: [
    ['a', '1000'],
    ['b', '2'],
    ['c', '1000'],
    ['d', '2'],
  ].map(([name, dim]) => ({ name, dim })),
}
