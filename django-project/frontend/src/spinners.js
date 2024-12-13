import React from 'react';
import { ClipLoader } from 'react-spinners';

const Spinner = ({ loading }) => (
    <ClipLoader color="#ffffff" loading={loading} size={20} />
);

export default Spinner;