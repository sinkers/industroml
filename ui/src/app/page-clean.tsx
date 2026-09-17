'use client';

import React, { useState, useEffect } from 'react';

export default function Home() {
  const [message, setMessage] = useState('Loading...');

  useEffect(() => {
    setMessage('Basic React is working!');
  }, []);

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold">IndustroML UI</h1>
      <p>{message}</p>
      <div className="mt-4">
        <button 
          onClick={() => setMessage('Button clicked!')}
          className="bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600"
        >
          Test Button
        </button>
      </div>
    </div>
  );
}