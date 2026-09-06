"use client";

import { useEffect } from "react";

export default function Home() {
  useEffect(() => {
    async function loadMeta() {
      const response = await fetch("/cases/case-000/meta.json");

      if (!response.ok) {
        throw new Error(`Failed to fetch meta.json: ${response.status}`);
      }

      const data = await response.json();

      console.log("CASE META:", data);
    }

    loadMeta();
  }, []);

  return (
    <main className="p-8">
      <h1 className="text-2xl font-bold">Naap</h1>
      <p>Checking case bundle...</p>
    </main>
  );
}
