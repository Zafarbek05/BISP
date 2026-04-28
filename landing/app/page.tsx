import { Download, Search, Shield, Zap, FileText, Database, Globe } from "lucide-react";

interface FeatureCardProps {
  icon: React.ReactNode;
  title: string;
  description: string;
}

function FeatureCard({ icon, title, description }: FeatureCardProps) {
  return (
    <div className="bg-white p-8 rounded-2xl shadow-sm border border-blue-50 hover:shadow-xl hover:shadow-blue-500/10 transition-all duration-300 transform hover:-translate-y-1">
      <div className="w-12 h-12 bg-blue-50 rounded-xl flex items-center justify-center mb-6 text-blue-600">
        {icon}
      </div>
      <h3 className="text-xl font-bold mb-3 text-blue-900">{title}</h3>
      <p className="text-slate-600 leading-relaxed">{description}</p>
    </div>
  );
}

export default function Home() {
  return (
    <div className="min-h-screen bg-white text-slate-900 font-sans selection:bg-blue-100 selection:text-blue-900">
      {/* Hero Section */}
      <section className="relative py-24 md:py-32 px-6 overflow-hidden bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-blue-100 via-blue-50 to-white">
        <div className="max-w-6xl mx-auto text-center relative z-10">
          <div className="inline-flex items-center px-4 py-1.5 mb-8 rounded-full bg-blue-600/10 text-blue-600 text-sm font-semibold tracking-wide">
            v1.0 is now available
          </div>
          <h1 className="text-5xl md:text-7xl font-extrabold tracking-tight text-blue-950 mb-8 leading-[1.1]">
            Private AI Search for your <br />
            <span className="text-blue-600 bg-clip-text">Local Files.</span>
          </h1>
          <p className="text-xl md:text-2xl text-slate-600 mb-12 max-w-3xl mx-auto leading-relaxed">
            Index your documents locally and chat with them using Gemini or local LLMs. 
            <span className="block font-medium text-blue-900 mt-2">No cloud required. No data leaks.</span>
          </p>
          <div className="flex flex-col sm:flex-row justify-center gap-4">
            <a 
              href="https://github.com/Zafarbek05/BISP/releases/download/v1.0.0/AI_Semantic_Search.exe"
              className="group relative inline-flex items-center justify-center px-8 py-4 font-bold text-white transition-all duration-300 bg-blue-600 rounded-2xl hover:bg-blue-700 shadow-[0_10px_20px_-10px_rgba(37,99,235,0.4)] hover:shadow-[0_20px_40px_-15px_rgba(37,99,235,0.5)] transform hover:-translate-y-1 active:translate-y-0"
            >
              <Download className="w-6 h-6 mr-2 transition-transform group-hover:scale-110" />
              Download v1.0 (Windows)
            </a>
          </div>
        </div>
        
        {/* Background decorative elements */}
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full h-full -z-0 pointer-events-none opacity-20">
          <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-blue-400 rounded-full blur-[120px]" />
          <div className="absolute bottom-[10%] right-[-5%] w-[30%] h-[30%] bg-blue-300 rounded-full blur-[100px]" />
        </div>
      </section>

      {/* How it Works Section */}
      <section className="py-24 px-6 bg-white">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-20">
            <h2 className="text-3xl md:text-5xl font-bold text-blue-950 mb-4">How it Works</h2>
            <div className="w-20 h-1.5 bg-blue-600 mx-auto rounded-full" />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-16 relative">
            {/* Connector lines (desktop only) */}
            <div className="hidden md:block absolute top-12 left-[20%] right-[20%] h-0.5 bg-blue-100 -z-0" />
            
            <div className="flex flex-col items-center relative z-10">
              <div className="w-24 h-24 bg-blue-600 text-white rounded-3xl flex items-center justify-center mb-8 text-3xl font-bold shadow-xl shadow-blue-600/20 rotate-3 hover:rotate-0 transition-transform duration-300">
                1
              </div>
              <h3 className="text-2xl font-bold mb-4 text-blue-950">Connect Folders</h3>
              <p className="text-slate-600 text-center leading-relaxed">
                Simply select the folders on your computer containing PDFs, documents, or code.
              </p>
            </div>
            
            <div className="flex flex-col items-center relative z-10">
              <div className="w-24 h-24 bg-blue-600 text-white rounded-3xl flex items-center justify-center mb-8 text-3xl font-bold shadow-xl shadow-blue-600/20 -rotate-3 hover:rotate-0 transition-transform duration-300">
                2
              </div>
              <h3 className="text-2xl font-bold mb-4 text-blue-950">Local Indexing</h3>
              <p className="text-slate-600 text-center leading-relaxed">
                The system builds a high-performance vector index locally using advanced embeddings.
              </p>
            </div>
            
            <div className="flex flex-col items-center relative z-10">
              <div className="w-24 h-24 bg-blue-600 text-white rounded-3xl flex items-center justify-center mb-8 text-3xl font-bold shadow-xl shadow-blue-600/20 rotate-3 hover:rotate-0 transition-transform duration-300">
                3
              </div>
              <h3 className="text-2xl font-bold mb-4 text-blue-950">Chat Privately</h3>
              <p className="text-slate-600 text-center leading-relaxed">
                Ask questions in natural language. Your LLM retrieves and synthesizes data instantly.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="py-24 px-6 bg-blue-50/50">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-20">
            <h2 className="text-3xl md:text-5xl font-bold text-blue-950 mb-4">Powerful Features</h2>
            <div className="w-20 h-1.5 bg-blue-600 mx-auto rounded-full" />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <FeatureCard 
              icon={<Search />}
              title="Semantic Search"
              description="Go beyond basic keywords. Find information based on meaning and context across thousands of files."
            />
            <FeatureCard 
              icon={<Shield />}
              title="100% Private"
              description="Your data never leaves your machine. Local indexing and local processing ensure total data sovereignty."
            />
            <FeatureCard 
              icon={<Zap />}
              title="Lightning Fast"
              description="Optimized local database engine designed for near-instant retrieval even with massive document sets."
            />
            <FeatureCard 
              icon={<Database />}
              title="Local LLM Support"
              description="Seamlessly integrate with Ollama to run models like Llama 3 or Mistral entirely offline."
            />
            <FeatureCard 
              icon={<FileText />}
              title="Multi-format Support"
              description="Native support for PDF, DOCX, TXT, MD, and dozens of programming languages."
            />
            <FeatureCard 
              icon={<Globe />}
              title="Hybrid Intelligence"
              description="Switch between local privacy and the power of Google Gemini when you need extra reasoning capacity."
            />
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-16 px-6 bg-white border-t border-blue-100">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row justify-between items-center gap-8">
          <div className="flex flex-col items-center md:items-start">
            <div className="text-blue-600 font-black text-2xl mb-2 tracking-tighter">HYBRID AI SEARCH</div>
            <p className="text-slate-500 text-sm">Secure, private, and local intelligence.</p>
          </div>
          <div className="flex gap-8 text-sm font-medium text-slate-600">
            <a href="#" className="hover:text-blue-600 transition-colors">Documentation</a>
            <a href="#" className="hover:text-blue-600 transition-colors">GitHub</a>
            <a href="#" className="hover:text-blue-600 transition-colors">Privacy</a>
          </div>
          <div className="text-slate-400 text-xs">
            © 2024 Hybrid AI Semantic Search System.
          </div>
        </div>
      </footer>
    </div>
  );
}
