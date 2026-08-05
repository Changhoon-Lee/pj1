import Lean.Elab.Tactic.Omega

namespace SACTAC

/-- T2 finite arithmetic core: fewer than N-q0+1 queries leave q0 unread. -/
theorem unread_of_fewer_queries {N q0 t : Nat}
    (hq : q0 ≤ N) (ht : t < N - q0 + 1) : q0 ≤ N - t := by
  omega

/-- T3 support-order core using the final valid prefix witness produced by the executable binder. -/
theorem lower_support_of_last_prefix
    {qH qTrue : Nat}
    (h : qH = 0 ∨ qH - 1 < qTrue) : qH ≤ qTrue := by
  omega

/-- T4 finite bottleneck core: every mandatory stage is bounded by the declared total. -/
theorem mandatoryStagesBounded
    {binding planning selected total : Nat}
    (hb : binding ≤ total) (hp : planning ≤ total) (hs : selected ≤ total) :
    binding ≤ total ∧ planning ≤ total ∧ selected ≤ total :=
  ⟨hb, hp, hs⟩

/-- T1 logical contract. The executable binder discharges the semantic premise. -/
theorem summaryConsistencyTrilemma
    (Sound Recomputed ProofVerified WorstCaseSound : Prop)
    (contract : Sound → Recomputed ∨ ProofVerified ∨ WorstCaseSound)
    (hs : Sound) : Recomputed ∨ ProofVerified ∨ WorstCaseSound :=
  contract hs

/-- T5 cross-multiplied finite crossover core. -/
theorem finiteCrossoverCrossProduct
    {L F C U : Nat} (hLF : L ≤ F) (hCU : C ≤ U) : L * C ≤ F * U := by
  calc
    L * C ≤ F * C := Nat.mul_le_mul_right C hLF
    _ ≤ F * U := Nat.mul_le_mul_left F hCU

/-- T6 state-local closure: a mandatory escalation predicate cannot authorize accept. -/
theorem noAcceptWhenEscalationRequired
    (mustEscalate accept : Bool)
    (rule : mustEscalate = true → accept = false)
    (h : mustEscalate = true) : accept = false :=
  rule h

/-- T7 endpoint separation: changing a reuse parameter does not alter one-shot cost. -/
theorem oneShotIndependentOfReuse (oneShot k₁ k₂ : Nat) :
    (fun _ : Nat => oneShot) k₁ = (fun _ : Nat => oneShot) k₂ := by
  rfl

end SACTAC
