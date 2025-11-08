import React, { useCallback, useEffect, useMemo, useState } from 'react';  
import {
  Box,
  Button,
  Flex,
  Heading,
  SimpleGrid,
  Stack,
  Tabs,
  TabList,
  Tab,
  TabPanels,
  TabPanel,
  Text,
  useToast,
} from '@chakra-ui/react';  
import axios from 'axios';  
import FileUpload from '../components/FileUpload';  
import FileList from '../components/FileList';  
import { useWebSocket } from '../context/WebSocketContext';  

const Dashboard = () => {  
  const [documents, setDocuments] = useState([]);  
  const [showAllProcessing, setShowAllProcessing] = useState(false);
  const [showAllProcessed, setShowAllProcessed] = useState(false);
  const { processingStatus, isConnected } = useWebSocket();  
  const toast = useToast();  

  const fetchDocuments = useCallback(async () => {  
    try {  
      const response = await axios.get('/api/documents');  
      setDocuments(response.data);  
    } catch (error) {  
      console.error("Failed to fetch documents:", error);  
      toast({  
        title: "Error",  
        description: "Failed to fetch documents",  
        status: "error",  
        duration: 5000,  
        isClosable: true,  
      });  
    }  
  }, [toast]);  

  useEffect(() => {  
    fetchDocuments();  
    // Set up refresh interval  
    const intervalId = setInterval(fetchDocuments, 15000);  
    return () => clearInterval(intervalId);  
  }, [fetchDocuments]);  

  // Merge document status with WebSocket status  
  const enhancedDocuments = useMemo(() => (
    documents.map((doc) => {
      const statusKey = doc?.filename || doc?.file_path || doc?.id;
      const wsStatus = statusKey ? processingStatus[statusKey] : undefined;
      const wsProgress = wsStatus && typeof wsStatus.progress === 'number' ? wsStatus.progress : undefined;
      const statusFromWs = wsStatus?.status;
      const pageCurrent = typeof wsStatus?.page_current === 'number' ? wsStatus.page_current : null;
      const pageTotal = typeof wsStatus?.page_total === 'number' ? wsStatus.page_total : null;

      let statusText = statusFromWs || (doc.processed ? 'Completed' : doc.processing ? 'Processing' : 'Queued');
      if (doc.error) {
        statusText = doc.error.startsWith('Error') ? doc.error : `Error: ${doc.error}`;
      }

      const dbProgress = typeof doc.progress === 'number' ? doc.progress : 0;
      let effectiveProgress = typeof wsProgress === 'number' ? wsProgress : dbProgress;

      if (statusFromWs) {
        const normalizedStatus = statusFromWs.toLowerCase();
        if (normalizedStatus.includes('completed')) {
          effectiveProgress = 100;
        } else if (normalizedStatus.includes('storing in vector database')) {
          effectiveProgress = Math.max(effectiveProgress, 75);
        } else if (normalizedStatus.includes('generating embeddings')) {
          effectiveProgress = Math.max(effectiveProgress, 70);
        } else if (normalizedStatus.includes('running ocr') && pageTotal && pageTotal > 0) {
          const ratio = Math.min(Math.max((pageCurrent || 0) / pageTotal, 0), 1);
          effectiveProgress = Math.max(effectiveProgress, 50 + ratio * 20);
        } else if (normalizedStatus.includes('parsing pdf') && pageTotal && pageTotal > 0) {
          const ratio = Math.min(Math.max((pageCurrent || 0) / pageTotal, 0), 1);
          effectiveProgress = Math.max(effectiveProgress, ratio * 50);
        }
      }

      if (!statusFromWs && doc.processing && !doc.processed) {
        effectiveProgress = Math.max(effectiveProgress, 1);
      }

      const clampedProgress = Number.isFinite(effectiveProgress)
        ? Math.max(0, Math.min(100, effectiveProgress))
        : 0;

      return {
        ...doc,
        wsStatus,
        progress: clampedProgress,
        statusText,
        pageCurrent,
        pageTotal,
      };
    })
  ), [documents, processingStatus]);

  const processingDocs = useMemo(
    () => enhancedDocuments.filter((doc) => !doc.processed),
    [enhancedDocuments],
  );

  const processedDocs = useMemo(
    () => enhancedDocuments.filter((doc) => doc.processed),
    [enhancedDocuments],
  );

  const sortedProcessingDocs = useMemo(() => {
    const docsCopy = [...processingDocs];
    docsCopy.sort((a, b) => {
      const progressDiff = (b.progress ?? 0) - (a.progress ?? 0);
      if (progressDiff !== 0) {
        return progressDiff;
      }
      const aDate = a.uploaded_at ? new Date(a.uploaded_at).getTime() : 0;
      const bDate = b.uploaded_at ? new Date(b.uploaded_at).getTime() : 0;
      return bDate - aDate;
    });
    return docsCopy;
  }, [processingDocs]);

  const sortedProcessedDocs = useMemo(() => {
    const docsCopy = [...processedDocs];
    docsCopy.sort((a, b) => {
      const aDate = a.uploaded_at ? new Date(a.uploaded_at).getTime() : 0;
      const bDate = b.uploaded_at ? new Date(b.uploaded_at).getTime() : 0;
      return bDate - aDate;
    });
    return docsCopy;
  }, [processedDocs]);

  const processingDisplayLimit = 100;
  const hasMoreProcessing = sortedProcessingDocs.length > processingDisplayLimit;
  const displayedProcessingDocs = useMemo(
    () => (showAllProcessing ? sortedProcessingDocs : sortedProcessingDocs.slice(0, processingDisplayLimit)),
    [showAllProcessing, sortedProcessingDocs],
  );

  const processedDisplayLimit = 200;
  const hasMoreProcessed = sortedProcessedDocs.length > processedDisplayLimit;
  const displayedProcessedDocs = useMemo(
    () => (showAllProcessed ? sortedProcessedDocs : sortedProcessedDocs.slice(0, processedDisplayLimit)),
    [showAllProcessed, sortedProcessedDocs],
  );

  const handleFileUploaded = () => {  
    // Refresh document list  
    fetchDocuments();  
  };  

  return (
    <Stack spacing={{ base: 6, lg: 8 }}>
      <Stack spacing={2}>
        <Heading as="h1" size={{ base: 'lg', md: 'xl' }}>MCP PDF Knowledge Base</Heading>
        <Text color="gray.600" fontSize={{ base: 'sm', md: 'md' }}>
          Upload documents, monitor ingestion, and manage your MCP connection in one place.
        </Text>
      </Stack>

      <SimpleGrid columns={{ base: 1, lg: 2 }} spacing={6}>
        <Box bg="white" p={{ base: 5, md: 6 }} shadow="md" borderRadius="lg">
          <Heading as="h2" size="md" mb={3}>
            Upload New PDF
          </Heading>
          <Text fontSize="sm" color="gray.600" mb={4}>
            PDFs are processed into searchable chunks and made available to MCP clients.
          </Text>
          <FileUpload onFileUploaded={handleFileUploaded} />
        </Box>

        <Box bg="white" p={{ base: 5, md: 6 }} shadow="md" borderRadius="lg">
          <Heading as="h2" size="md" mb={3}>
            MCP Connection Status
          </Heading>
          <Text
            color={isConnected ? 'green.500' : 'red.500'}
            fontWeight="semibold"
            fontSize={{ base: 'md', md: 'lg' }}
          >
            {isConnected ? 'Connected' : 'Disconnected'}
          </Text>
          <Text fontSize="sm" color="gray.600" mt={3}>
            Configure in your AI/LLM chat client: Settings → MCP Servers → Add URL
            {': '}http://MCP-SERVER-IP:DOCKER_PORT/mcp
          </Text>
        </Box>
      </SimpleGrid>

      <Box bg="white" p={{ base: 5, md: 6 }} shadow="md" borderRadius="lg">
        <Heading as="h2" size="md" mb={4}>
          Your Documents
        </Heading>

        <Tabs variant="soft-rounded" colorScheme="blue" isFitted>
          <TabList>
            <Tab>Processing ({sortedProcessingDocs.length})</Tab>  
            <Tab>Completed ({sortedProcessedDocs.length})</Tab>  
          </TabList>

          <TabPanels>
            <TabPanel px={{ base: 0, md: 2 }}>
              {sortedProcessingDocs.length > 0 ? (
                <Stack spacing={4}>
                  <Flex direction={{ base: 'column', md: 'row' }} justify="space-between" gap={3}>
                    <Text color="gray.600" fontSize="sm">
                      Showing {displayedProcessingDocs.length} of {sortedProcessingDocs.length} processing documents.
                    </Text>
                    {hasMoreProcessing && (
                      <Button size="sm" variant="outline" onClick={() => setShowAllProcessing((prev) => !prev)}>
                        {showAllProcessing ? 'Show fewer' : `Show all (${sortedProcessingDocs.length})`}
                      </Button>
                    )}
                  </Flex>
                  <FileList
                    documents={displayedProcessingDocs}
                    onDeleteDocument={fetchDocuments}
                    showProgress={true}
                  />
                </Stack>
              ) : (
                <Text color="gray.500">No documents currently processing</Text>
              )}
            </TabPanel>

            <TabPanel px={{ base: 0, md: 2 }}>
              {sortedProcessedDocs.length > 0 ? (
                <Stack spacing={4}>
                  <Flex direction={{ base: 'column', md: 'row' }} justify="space-between" gap={3}>
                    <Text color="gray.600" fontSize="sm">
                      Showing {displayedProcessedDocs.length} of {sortedProcessedDocs.length} processed documents.
                    </Text>
                    {hasMoreProcessed && (
                      <Button size="sm" variant="outline" onClick={() => setShowAllProcessed((prev) => !prev)}>
                        {showAllProcessed ? 'Show fewer' : `Show all (${sortedProcessedDocs.length})`}
                      </Button>
                    )}
                  </Flex>
                  <FileList
                    documents={displayedProcessedDocs}
                    onDeleteDocument={fetchDocuments}
                    showProgress={false}
                  />
                </Stack>
              ) : (
                <Text color="gray.500">No processed documents yet</Text>
              )}
            </TabPanel>
          </TabPanels>
        </Tabs>
      </Box>
    </Stack>
  );  
};  

export default Dashboard;