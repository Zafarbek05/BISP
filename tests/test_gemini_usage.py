import unittest
from unittest.mock import MagicMock, patch
import os
import sys

# Mock sys.modules for problematic imports before they are loaded
sys.modules['db_cipher'] = MagicMock()
sys.modules['bcrypt'] = MagicMock()
sys.modules['sentence_transformers'] = MagicMock()
sys.modules['numpy'] = MagicMock()

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

# Mock storage to avoid DB init issues
sys.modules['processed_storage'] = MagicMock()

import src.chat_storage as db
import src.rag_final_answer as rag

class TestGeminiUsage(unittest.TestCase):
    
    @patch('chat_storage.save_gemini_usage')
    def test_parse_429_error(self, mock_save):
        """Test parsing of 429 error messages to extract limits."""
        error_msg = "429 Quota exceeded for metric: generate_content_free_tier_requests, limit: 15, model: gemini-2.5-flash"
        
        # Simulate a 429 error in generate_with_gemini
        with patch('rag_final_answer.get_genai_client') as mock_client:
            mock_gen = mock_client.return_value.models.generate_content
            mock_gen.side_effect = Exception(error_msg)
            
            with self.assertRaises(Exception):
                rag.generate_with_gemini("hi", "instr", "gemini-2.5-flash")
            
            # Verify save_gemini_usage was called with parsed limit
            mock_save.assert_called()
            args, kwargs = mock_save.call_args
            self.assertEqual(kwargs.get('limit_rpm'), 15)
            self.assertEqual(kwargs.get('remaining_rpm'), 0)
            self.assertEqual(kwargs.get('model_name'), "gemini-2.5-flash")

    @patch('chat_storage.save_gemini_usage')
    def test_successful_usage_tracking(self, mock_save):
        """Test tracking usage tokens from successful response."""
        with patch('rag_final_answer.get_genai_client') as mock_client:
            mock_resp = MagicMock()
            mock_resp.text = "Hello"
            mock_resp.usage_metadata.total_token_count = 100
            mock_client.return_value.models.generate_content.return_value = mock_resp
            
            rag.generate_with_gemini("hi", "instr", "gemini-2.5-flash")
            
            mock_save.assert_called()
            args, kwargs = mock_save.call_args
            self.assertEqual(kwargs.get('quota_consumed'), 100)
            self.assertEqual(kwargs.get('model_name'), "gemini-2.5-flash")

if __name__ == '__main__':
    unittest.main()
