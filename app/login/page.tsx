"use client";

import { useState } from "react";
import Image from "next/image";
import { signIn } from "next-auth/react";

export default function LoginPage() {
  const [isLoading, setIsLoading] = useState(false);
  const linkedinEnabled = process.env.NEXT_PUBLIC_LINKEDIN_ENABLED === "true";

  const handleLinkedInLogin = async () => {
    setIsLoading(true);
    await signIn("linkedin", { callbackUrl: "/" });
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl p-8 max-w-md w-full text-center">
        <div className="mb-6">
          <Image src="/logo.png" alt="Garje Marathi" width={64} height={64} className="h-16 w-16 mx-auto" />
          <h1 className="text-3xl font-bold text-indigo-900 mt-4">Garje Marathi AI</h1>
          <p className="text-gray-600 mt-2">Community Assistant · तुमचा digital साथीदार</p>
        </div>

        <div className="space-y-4">
          <p className="text-gray-700">
            Community Chat वापरण्यासाठी LinkedIn ने sign in करा.
          </p>

          <button
            onClick={handleLinkedInLogin}
            disabled={isLoading || !linkedinEnabled}
            className="w-full flex items-center justify-center gap-2 bg-[#0a66c2] text-white py-3 px-4 rounded-lg hover:bg-[#004182] disabled:opacity-50 disabled:cursor-not-allowed transition"
          >
            LinkedIn ने Sign in करा
          </button>
          {!linkedinEnabled && <p className="text-sm text-red-600">LinkedIn login is not configured yet.</p>}
        </div>

        <p className="text-xs text-gray-500 mt-6">
          Sign in करून तुम्ही आमच्या terms of service शी सहमत होता.
        </p>
      </div>
    </div>
  );
}
