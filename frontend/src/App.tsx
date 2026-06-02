import { Routes, Route, Navigate } from "react-router-dom";

import { Nav } from "@/components/Nav";
import { Footer } from "@/components/Footer";
import { StrategiePage } from "@/pages/Strategie";
import { ProjetPage } from "@/pages/Projet";
import { IfcPage } from "@/pages/Ifc";
import { MarketplacePage } from "@/pages/Marketplace";
import { MarketplaceCompanyPage } from "@/pages/MarketplaceCompany";
import { MarketplaceGroupOrdersPage } from "@/pages/MarketplaceGroupOrders";

export default function App() {
  return (
    <div className="h-screen flex flex-col">
      <Nav />
      <main className="flex-1 flex flex-col min-h-0 overflow-y-auto">
        <Routes>
          <Route path="/" element={<Navigate to="/strategie" replace />} />
          <Route path="/strategie" element={<StrategiePage />} />
          <Route path="/projet" element={<ProjetPage />} />
          <Route path="/projet/:id" element={<ProjetPage />} />
          <Route path="/ifc" element={<IfcPage />} />
          <Route path="/marketplace" element={<MarketplacePage />} />
          <Route path="/marketplace/commandes-groupees" element={<MarketplaceGroupOrdersPage />} />
          <Route path="/marketplace/:slug" element={<MarketplaceCompanyPage />} />
          <Route path="*" element={<Navigate to="/strategie" replace />} />
        </Routes>
      </main>
      <Footer />
    </div>
  );
}
