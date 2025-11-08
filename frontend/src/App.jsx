import React from 'react';  
import { ChakraProvider, Box, Container } from '@chakra-ui/react';  
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';  
import Header from './components/Header';  
import Dashboard from './pages/Dashboard';  
import PDFView from './pages/PDFView';
import Search from './pages/Search';
import Settings from './pages/Settings';
import { WebSocketProvider } from './context/WebSocketContext';  

function App() {  
  return (  
    <ChakraProvider>  
      <WebSocketProvider>  
        <Router>  
          <Box minH="100vh" bgGradient="linear(to-br, gray.50, gray.100)">  
            <Header />  
            <Container maxW="container.xl" py={{ base: 6, md: 10 }} px={{ base: 4, md: 8 }}>  
              <Routes>  
                <Route path="/" element={<Dashboard />} />  
                <Route path="/search" element={<Search />} />
                <Route path="/pdf/:id" element={<PDFView />} />
                <Route path="/settings" element={<Settings />} />
              </Routes>  
            </Container>  
          </Box>  
        </Router>  
      </WebSocketProvider>  
    </ChakraProvider>  
  );  
}  

export default App;