import Mathlib

/-!
# Bare-bones Lean scaffold for the tau_perp problem

This file intentionally mixes executable definitions with theorem statements whose
proofs are left as `sorry`.  The point is to pin down the finite objects:

* `tauPerp n`: number of adjacent coprime divisor pairs of `n`.
* `squarefreeDivisor p S`: the divisor indexed by a subset `S` of the prime set.
* `subsetWeight w S`: the log/subset-sum model.

The first serious formal target is:

  `Nat.gcd (squarefreeDivisor p S) (squarefreeDivisor p T) = 1 ↔ Disjoint S T`

for injective prime-labelled squarefree products.
-/

open scoped BigOperators

namespace TauPerp

/-- Consecutive pairs in a list. -/
def adjacentPairs {α : Type _} : List α → List (α × α)
  | [] => []
  | [_] => []
  | a :: b :: rest => (a, b) :: adjacentPairs (b :: rest)

/-- Divisors of `n`, listed in increasing order. -/
def divisorListSorted (n : Nat) : List Nat :=
  ((Finset.range (n + 1)).filter (fun d => d ≠ 0 ∧ d ∣ n)).sort (· ≤ ·)

/--
`tauPerp n` counts adjacent divisor pairs `(d_i,d_{i+1})` with gcd equal to `1`.
This is the function denoted `τ_⊥(n)` in the problem statement.
-/
def tauPerp (n : Nat) : Nat :=
  ((adjacentPairs (divisorListSorted n)).filter
    (fun ab => Nat.gcd ab.1 ab.2 = 1)).length

/-- Squarefree divisor indexed by a subset of the prime labels. -/
def squarefreeDivisor {k : Nat} (p : Fin k → Nat)
    (S : Finset (Fin k)) : Nat :=
  ∏ i in S, p i

/-- Additive weight of a subset.  Eventually `w i = Real.log (p i)`. -/
def subsetWeight {k : Nat} (w : Fin k → ℝ)
    (S : Finset (Fin k)) : ℝ :=
  ∑ i in S, w i

/-- Generic weights: positive and with all subset sums distinct. -/
def GenericWeights {k : Nat} (w : Fin k → ℝ) : Prop :=
  (∀ i, 0 < w i) ∧
  ∀ S T : Finset (Fin k),
    subsetWeight w S = subsetWeight w T → S = T

/-- Ordered subsets under a generic weight vector.

This is the Boolean-cube analogue of the increasing divisor list.
-/
noncomputable def orderedSubsets {k : Nat} (w : Fin k → ℝ) : List (Finset (Fin k)) :=
  (Finset.univ : Finset (Finset (Fin k))).sort
    (fun S T => subsetWeight w S ≤ subsetWeight w T)

/-- Number of adjacent disjoint subset pairs in the subset-sum order. -/
noncomputable def adjDisjointCount {k : Nat} (w : Fin k → ℝ) : Nat :=
  ((adjacentPairs (orderedSubsets w)).filter
    (fun ST => Disjoint ST.1 ST.2)).length

/-! ## First arithmetic bridge lemmas -/

/-- A prime label divides the squarefree divisor exactly when its index is in the subset.

This is probably the first useful lemma to prove by induction over `S` or by using
mathlib lemmas about primes dividing finite products.
-/
theorem prime_dvd_squarefreeDivisor_iff_mem
    {k : Nat}
    {p : Fin k → Nat}
    (hpPrime : ∀ i, Nat.Prime (p i))
    (hpInj : Function.Injective p)
    (j : Fin k)
    (S : Finset (Fin k)) :
    p j ∣ squarefreeDivisor p S ↔ j ∈ S := by
  sorry

/-- Coprimality of squarefree divisors is the same as disjointness of supports. -/
theorem gcd_squarefreeDivisor_eq_one_iff_disjoint
    {k : Nat}
    {p : Fin k → Nat}
    (hpPrime : ∀ i, Nat.Prime (p i))
    (hpInj : Function.Injective p)
    (S T : Finset (Fin k)) :
    Nat.gcd (squarefreeDivisor p S) (squarefreeDivisor p T) = 1
      ↔ Disjoint S T := by
  sorry

/-! ## Log/subset-sum bridge lemmas -/

/-- Log of a squarefree divisor is the sum of the logs of its chosen prime labels. -/
theorem Real.log_squarefreeDivisor
    {k : Nat}
    {p : Fin k → Nat}
    (hpPrime : ∀ i, Nat.Prime (p i))
    (S : Finset (Fin k)) :
    Real.log (squarefreeDivisor p S)
      = subsetWeight (fun i => Real.log (p i)) S := by
  sorry

/-- Multiplicative order of squarefree divisors equals additive order of log weights. -/
theorem squarefreeDivisor_lt_iff_subsetWeight_lt
    {k : Nat}
    {p : Fin k → Nat}
    (hpPrime : ∀ i, Nat.Prime (p i))
    (S T : Finset (Fin k)) :
    squarefreeDivisor p S < squarefreeDivisor p T ↔
      subsetWeight (fun i => Real.log (p i)) S
        < subsetWeight (fun i => Real.log (p i)) T := by
  sorry

/-! ## The intended high-level reduction statement -/

/--
Intended main bridge theorem: for a squarefree product of distinct primes, `tauPerp`
is the adjacent-disjoint-pair count in the log subset-sum ordering.

This is deliberately left as a theorem statement.  Proving it will require an
equivalence between divisors of `∏ i, p i` and subsets of `Fin k`, plus order
transport using `squarefreeDivisor_lt_iff_subsetWeight_lt`.
-/
theorem tauPerp_squarefree_eq_adjDisjointCount
    {k : Nat}
    {p : Fin k → Nat}
    (hpPrime : ∀ i, Nat.Prime (p i))
    (hpInj : Function.Injective p)
    (hgeneric : GenericWeights (fun i => Real.log (p i))) :
    tauPerp (∏ i, p i) =
      adjDisjointCount (fun i => Real.log (p i)) := by
  sorry

/-! ## Small computational checks

If the executable definition above is accepted by Lean/mathlib, these `#eval`s
should return the primorial values discussed in the notes.
-/

#eval tauPerp 2       -- expected: 1
#eval tauPerp 6       -- expected: 2
#eval tauPerp 30      -- expected: 4
#eval tauPerp 210     -- expected: 7
#eval tauPerp 2310    -- expected: 12
#eval tauPerp 30030   -- expected: 17

/-- Example lower-bound certificate for the squarefree extremal problem. -/
theorem tauPerp_2310_eq_12 : tauPerp 2310 = 12 := by
  native_decide

/-- Example lower-bound certificate for the squarefree extremal problem. -/
theorem tauPerp_30030_eq_17 : tauPerp 30030 = 17 := by
  native_decide

end TauPerp
