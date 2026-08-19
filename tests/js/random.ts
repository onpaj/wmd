/** Deterministic Math.random replacement so shuffles are reproducible across a test run. */

const LCG_MULTIPLIER = 1103515245;
const LCG_INCREMENT = 12345;
const LCG_MODULUS = 2147483648;

interface MethodMocker {
  method(target: object, name: string, implementation: () => number): unknown;
}

export function mockRandom(mock: MethodMocker, seed = 42): void {
  let state = seed;
  mock.method(Math, 'random', () => {
    state = (state * LCG_MULTIPLIER + LCG_INCREMENT) % LCG_MODULUS;
    return state / LCG_MODULUS;
  });
}
