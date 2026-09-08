import unittest
from memsolver import llm, simconfig


class TestLLM(unittest.TestCase):
    def test_seeded_rng_deterministic(self):
        # Same inputs -> identical draws
        r1 = llm.seeded_rng("case-1", "small", 0, "gen")
        r2 = llm.seeded_rng("case-1", "small", 0, "gen")
        # Draw a sequence
        seq1 = [r1.randint(1, 1000) for _ in range(10)]
        seq2 = [r2.randint(1, 1000) for _ in range(10)]
        self.assertEqual(seq1, seq2)

    def test_different_attempt_different_draw(self):
        r1 = llm.seeded_rng("case-1", "small", 0, "gen")
        r2 = llm.seeded_rng("case-1", "small", 1, "gen")
        self.assertNotEqual(r1.randint(1, 1000), r2.randint(1, 1000))

    def test_different_purpose_different_draw(self):
        r1 = llm.seeded_rng("case-1", "small", 0, "gen")
        r2 = llm.seeded_rng("case-1", "small", 0, "verify")
        self.assertNotEqual(r1.randint(1, 1000), r2.randint(1, 1000))

    def test_simulated_llm_deterministic_across_instances(self):
        client1 = llm.SimulatedLLM()
        client2 = llm.SimulatedLLM()
        rng1 = llm.seeded_rng("case-1", "small", 0, "gen")
        rng2 = llm.seeded_rng("case-1", "small", 0, "gen")
        messages = [{"role": "user", "content": "Hello"}]
        call1 = client1.complete(messages, "small", 500, rng1, "easy", "gen")
        call2 = client2.complete(messages, "small", 500, rng2, "easy", "gen")
        self.assertEqual(call1.input_tokens, call2.input_tokens)
        self.assertEqual(call1.output_tokens, call2.output_tokens)
        self.assertEqual(call1.latency_ms, call2.latency_ms)
        self.assertEqual(call1.cost, call2.cost)

    def test_count_input_tokens(self):
        client = llm.SimulatedLLM()
        # 100 content chars, but the heuristic counts the whole serialized
        # message: keys, quotes and separators add ~31 chars -> ceil(131/4)=33.
        messages = [{"role": "user", "content": "a" * 100}]
        tokens = client.count_input_tokens(messages)
        self.assertEqual(tokens, 33)

    def test_max_tokens_clamping(self):
        client = llm.SimulatedLLM()
        rng = llm.seeded_rng("case-clamp", "small", 0, "gen")
        # Force a draw that would exceed max_tokens by using a high difficulty with large out_tokens range
        call = client.complete([{"role": "user", "content": "x"}], "small", 10, rng, "easy", "gen")
        self.assertLessEqual(call.output_tokens, 10)

    def test_openai_stub_raises(self):
        client = llm.OpenAICompatClient()
        with self.assertRaises(NotImplementedError):
            client.complete([], "small", 100, llm.seeded_rng("x", "s", 0), "easy", "gen")


if __name__ == "__main__":
    unittest.main()
