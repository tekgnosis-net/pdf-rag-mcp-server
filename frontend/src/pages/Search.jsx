import React, { useCallback, useState } from 'react';
import {
  Badge,
  Box,
  Button,
  Flex,
  Heading,
  HStack,
  Input,
  Modal,
  ModalBody,
  ModalCloseButton,
  ModalContent,
  ModalFooter,
  ModalHeader,
  ModalOverlay,
  NumberInput,
  NumberInputField,
  Spinner,
  Stack,
  Text,
  Tooltip,
  useDisclosure,
  useToast,
} from '@chakra-ui/react';
import { FiBookOpen, FiSearch } from 'react-icons/fi';
import ReactMarkdown from 'react-markdown';
import { fetchDocumentMarkdown, searchDocuments } from '../api/documents';

const clampLimit = (value) => {
  if (Number.isNaN(value) || value == null) {
    return 10;
  }
  return Math.min(50, Math.max(1, value));
};

const Search = () => {
  const [query, setQuery] = useState('');
  const [limit, setLimit] = useState(10);
  const [results, setResults] = useState([]);
  const [isSearching, setIsSearching] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [selectedResult, setSelectedResult] = useState(null);
  const [markdownContent, setMarkdownContent] = useState('');
  const [loadingMarkdown, setLoadingMarkdown] = useState(false);
  const [requestedLimit, setRequestedLimit] = useState(limit);

  const toast = useToast();
  const { isOpen, onOpen, onClose } = useDisclosure();

  const executeSearch = useCallback(
    async () => {
      const trimmed = query.trim();
      if (!trimmed) {
        toast({
          title: 'Enter a search query',
          status: 'warning',
        });
        return;
      }

      setIsSearching(true);
      try {
        const payload = await searchDocuments({ query: trimmed, limit });
        setResults(payload.results || []);
        setRequestedLimit(payload.limit ?? limit);
        setHasSearched(true);
      } catch (err) {
        console.error('Search failed', err);
        toast({
          title: 'Search failed',
          description: err?.response?.data?.detail || 'Please try again in a moment.',
          status: 'error',
        });
      } finally {
        setIsSearching(false);
      }
    },
    [query, limit, toast]
  );

  const handleSubmit = () => {
    executeSearch();
  };

  const handleViewMarkdown = async (result) => {
    if (!result?.pdf_id) {
      toast({ title: 'Unable to load markdown for this result', status: 'warning' });
      return;
    }
    setSelectedResult(result);
    setMarkdownContent('');
    setLoadingMarkdown(true);
    onOpen();
    try {
      const payload = await fetchDocumentMarkdown({
        id: result.pdf_id,
        start_page: result.page || 1,
        max_pages: 1,
      });
      setMarkdownContent(payload.markdown || '');
    } catch (err) {
      console.error('Failed to load markdown', err);
      toast({
        title: 'Failed to load markdown',
        description: err?.response?.data?.detail || 'Please try again later.',
        status: 'error',
      });
    } finally {
      setLoadingMarkdown(false);
    }
  };

  const renderResultPreview = (content) => {
    if (!content) {
      return 'No preview available.';
    }
    const trimmed = content.trim();
    if (trimmed.length <= 220) {
      return trimmed;
    }
    return `${trimmed.slice(0, 220)}…`;
  };

  return (
    <Stack spacing={6}>
      <Stack spacing={2}>
        <Heading as="h1" size="lg">
          Semantic Search
        </Heading>
        <Text color="gray.600">
          Search across processed PDF content and jump directly into the rendered markdown for any match.
        </Text>
      </Stack>

      <Box bg="white" p={{ base: 4, md: 6 }} shadow="md" borderRadius="lg">
        <Stack spacing={4} direction={{ base: 'column', md: 'row' }} align="flex-end">
          <Box flex="1">
            <Text fontSize="sm" fontWeight="medium" mb={1}>
              Query
            </Text>
            <Input
              placeholder="Search for topics, phrases, or keywords"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') {
                  handleSubmit();
                }
              }}
            />
          </Box>

          <Box w={{ base: '100%', md: '160px' }}>
            <Text fontSize="sm" fontWeight="medium" mb={1}>
              Number of results
            </Text>
            <NumberInput
              min={1}
              max={50}
              value={limit}
              onChange={(_, valueAsNumber) => setLimit(clampLimit(valueAsNumber))}
            >
              <NumberInputField />
            </NumberInput>
          </Box>

          <Button
            colorScheme="blue"
            leftIcon={<FiSearch />}
            minW={{ base: '100%', md: '140px' }}
            isLoading={isSearching}
            onClick={handleSubmit}
          >
            Search
          </Button>
        </Stack>
      </Box>

      <Box bg="white" p={{ base: 4, md: 6 }} shadow="md" borderRadius="lg">
        {isSearching ? (
          <Box textAlign="center" py={12}>
            <Spinner size="xl" />
            <Text mt={4}>Searching the knowledge base…</Text>
          </Box>
        ) : results.length === 0 ? (
          <Box py={6} textAlign="center">
            <Text color="gray.500">
              {hasSearched
                ? 'No matches found. Try a different query or broaden your keywords.'
                : 'Run a search to see relevant content across your PDFs.'}
            </Text>
          </Box>
        ) : (
          <Stack spacing={4}>
            <Text fontSize="sm" color="gray.600">
              Showing {results.length} result{results.length === 1 ? '' : 's'} (max {requestedLimit})
            </Text>

            <Stack spacing={4}>
              {results.map((result, index) => {
                const relevance = Number.isFinite(result?.relevance)
                  ? Math.max(0, Math.min(1, result.relevance))
                  : null;
                const scoreLabel = relevance != null ? `${(relevance * 100).toFixed(1)}% match` : 'Score unavailable';
                const pageLabel = result?.page ? `Page ${result.page}` : 'Page unknown';

                return (
                  <Box key={`${result.pdf_id || 'unknown'}-${index}`} borderWidth="1px" borderRadius="lg" p={4}>
                    <Stack spacing={2}>
                      <Flex justify="space-between" align={{ base: 'flex-start', md: 'center' }} direction={{ base: 'column', md: 'row' }}>
                        <HStack spacing={3} mb={{ base: 2, md: 0 }}>
                          <Badge colorScheme="blue">#{index + 1}</Badge>
                          <Text fontWeight="semibold">{result?.filename || 'Unknown document'}</Text>
                        </HStack>
                        <HStack spacing={3}>
                          <Tooltip label={scoreLabel}>
                            <Badge colorScheme="purple">{scoreLabel}</Badge>
                          </Tooltip>
                          <Badge colorScheme="gray">{pageLabel}</Badge>
                        </HStack>
                      </Flex>

                      <Text color="gray.700" fontSize="sm">
                        {renderResultPreview(result?.content)}
                      </Text>

                      <Button
                        leftIcon={<FiBookOpen />}
                        alignSelf="flex-start"
                        size="sm"
                        colorScheme="purple"
                        onClick={() => handleViewMarkdown(result)}
                      >
                        View Markdown
                      </Button>
                    </Stack>
                  </Box>
                );
              })}
            </Stack>
          </Stack>
        )}
      </Box>

      <Modal isOpen={isOpen} onClose={onClose} size="5xl">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>
            {selectedResult
              ? `Markdown view: ${selectedResult.filename || 'Document'}`
              : 'Markdown view'}
          </ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            {loadingMarkdown ? (
              <Box textAlign="center" py={8}>
                <Spinner size="lg" />
                <Text mt={4}>Loading markdown…</Text>
              </Box>
            ) : markdownContent ? (
              <Box maxHeight="60vh" overflowY="auto" borderWidth="1px" borderRadius="md" p={4} bg="gray.50">
                <ReactMarkdown>{markdownContent}</ReactMarkdown>
              </Box>
            ) : (
              <Text color="red.500">No markdown content available.</Text>
            )}
          </ModalBody>
          <ModalFooter>
            <Button onClick={onClose}>Close</Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </Stack>
  );
};

export default Search;
