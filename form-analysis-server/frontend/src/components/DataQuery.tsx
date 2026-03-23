import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "./ui/table";
import { Search, Download } from "lucide-react";

interface QueryResult {
  id: number;
  filename: string;
  upload_date: string;
  status: string;
  records: number;
}

export function DataQuery() {
  const { t } = useTranslation();
  const [searchTerm, setSearchTerm] = useState("");
  const [isSearching, setIsSearching] = useState(false);
  const [results, setResults] = useState<QueryResult[]>([]);

  // Mock data for demonstration
  const mockData: QueryResult[] = [
    {
      id: 1,
      filename: "p1_2503033_03.csv",
      upload_date: "2025-11-08 14:30:00",
      status: "completed",
      records: 150
    },
    {
      id: 2,
      filename: "p2_2503033_03.csv", 
      upload_date: "2025-11-08 14:32:00",
      status: "completed",
      records: 280
    },
    {
      id: 3,
      filename: "p3_data_analysis.csv",
      upload_date: "2025-11-08 14:35:00", 
      status: "processing",
      records: 95
    }
  ];

  const getStatusLabel = (status: string) => {
    if (status === "completed") return t("dataQuery.status.completed");
    if (status === "processing") return t("dataQuery.status.processing");
    return status;
  };

  const handleSearch = async () => {
    setIsSearching(true);
    
    try {
      // TODO: Replace with actual API call
      // const response = await fetch(`/api/search?q=${searchTerm}`);
      // const data = await response.json();
      
      // Simulate API delay
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      // Filter mock data based on search term
      const needle = searchTerm.toLowerCase();
      const filteredResults = mockData.filter(item => 
        item.filename.toLowerCase().includes(needle) ||
        getStatusLabel(item.status).toLowerCase().includes(needle)
      );
      
      setResults(filteredResults);
    } catch (error) {
      console.error('Search failed:', error);
    } finally {
      setIsSearching(false);
    }
  };

  const handleExport = (filename: string) => {
    // TODO: Implement actual export functionality
    console.log(`Exporting data for: ${filename}`);
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-lg font-semibold text-gray-700">{t("dataQuery.title")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-2">
            <Input
              placeholder={t("dataQuery.searchPlaceholder")}
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
              className="flex-1"
            />
            <Button 
              onClick={handleSearch}
              disabled={isSearching}
              className="flex items-center gap-2"
            >
              <Search className="w-4 h-4" />
              {isSearching ? t("dataQuery.searching") : t("dataQuery.search")}
            </Button>
          </div>
          
          <div className="text-sm text-gray-500">
            {t("dataQuery.hint")}
          </div>
        </CardContent>
      </Card>

      {results.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg font-semibold text-gray-700">
              {t("dataQuery.resultsWithCount", { count: results.length })}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="border rounded-lg overflow-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="font-semibold">{t("dataQuery.columns.filename")}</TableHead>
                    <TableHead className="font-semibold">{t("dataQuery.columns.uploadTime")}</TableHead>
                    <TableHead className="font-semibold">{t("dataQuery.columns.status")}</TableHead>
                    <TableHead className="font-semibold">{t("dataQuery.columns.records")}</TableHead>
                    <TableHead className="font-semibold">{t("dataQuery.columns.actions")}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {results.map((item) => (
                    <TableRow key={item.id}>
                      <TableCell className="font-medium">{item.filename}</TableCell>
                      <TableCell>{item.upload_date}</TableCell>
                      <TableCell>
                        <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                          item.status === 'completed' 
                            ? 'bg-green-100 text-green-700' 
                            : 'bg-yellow-100 text-yellow-700'
                        }`}>
                          {getStatusLabel(item.status)}
                        </span>
                      </TableCell>
                      <TableCell>{item.records.toLocaleString()}</TableCell>
                      <TableCell>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleExport(item.filename)}
                          className="flex items-center gap-1"
                          disabled={item.status !== 'completed'}
                        >
                          <Download className="w-3 h-3" />
                          {t("dataQuery.export")}
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>
      )}

      {searchTerm && results.length === 0 && !isSearching && (
        <Card>
          <CardContent className="py-8 text-center text-gray-500">
            <p>{t("dataQuery.empty.noMatch")}</p>
            <p className="text-sm mt-1">{t("dataQuery.empty.tryDifferent")}</p>
          </CardContent>
        </Card>
      )}

      {!searchTerm && results.length === 0 && (
        <Card>
          <CardContent className="py-8 text-center text-gray-500">
            <Search className="w-12 h-12 mx-auto mb-3 text-gray-300" />
            <p>{t("dataQuery.empty.prompt")}</p>
            <p className="text-sm mt-1">{t("dataQuery.empty.supportsKeywords")}</p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}