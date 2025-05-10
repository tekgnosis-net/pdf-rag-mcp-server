import React from 'react';  
import { ChakraProvider, Box, Container } from '@chakra-ui/react';  
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';  
import Header from './components/Header';  
import Dashboard from './pages/Dashboard';  
import PDFView from './pages/PDFView';  
import { WebSocketProvider } from './context/WebSocketContext';  

function App() {  
  return (  
    <ChakraProvider>  
      <WebSocketProvider>  
        <Router>  
          <Box minH="100vh" bg="gray.50">  
            <Header />  
            <Container maxW="container.xl" py={8}>  
              <Routes>  
                <Route path="/" element={<Dashboard />} />  
                <Route path="/pdf/:id" element={<PDFView />} />  
              </Routes>  
            </Container>  
          </Box>  
        </Router>  
      </WebSocketProvider>  
    </ChakraProvider>  
  );  
}  

export default App;