-- Modificari aduse in baza de date primita

CREATE TABLE IF NOT EXISTS superhero_api.users(
    id INT AUTO_INCREMENT PRIMARY KEY ,
    username VARCHAR(50) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    role ENUM('admin','user') NOT NULL DEFAULT 'user'
);

--Adaugat manual de noi pt securitate, doar adminul va putea sa faca insert/update/delete
--Restul utilizatorilor care se inregistreaza pe aplicatie, vor avea rolul by default 'user'
-- username : admin
-- password : admin123
INSERT INTO superhero_api.users (username,password,role)
VALUES('admin','$2b$12$8J9oz7wHLeUNFC8VWFLce.xFCCo47Ng9n.ut9sRci0Ze1bnxRBhLa','admin');

--Verificare insert in db
SELECT id,
       JSON_UNQUOTE(JSON_EXTRACT(data, '$.name')) AS name
FROM superhero_api.data
WHERE JSON_UNQUOTE(JSON_EXTRACT(data, '$.name')) = 'Mos Craciun';